from flask import Flask, render_template, request, flash, redirect, abort, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import pymysql
from dynaconf import Dynaconf


app = Flask(__name__)

config = Dynaconf(settings_file =["settings.toml"])

app.secret_key = config.secret_key

login_manager = LoginManager(app)

login_manager.login_view = "/login"

class User:
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def __init__(self, result):
        self.name = result["Name"]
        self.email = result["Email"]
        self.address = result["Address"]
        self.id = result["ID"]

    def get_id(self):
        return str(self.id)
    

@login_manager.user_loader  
def load_user(user_id):
    connection  = connect_db()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM `User` WHERE `ID` = %s ", (user_id))

    result = cursor.fetchone()
    connection.close()
    if result is None:
        return None

    
    return User(result)


def connect_db():
    conn = pymysql.connect(
        host="db.steamcenter.tech",
        user="cogboe",
        password = config.password,
        database="cogboe_heekaudio",
        autocommit= True,
        cursorclass= pymysql.cursors.DictCursor
    )
    return conn


@app.route("/")
def index():
    return render_template("homepage.html.jinja")

@app.route("/search")
def search():
    query = request.args.get("q", "").strip()

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM Product
        WHERE Name LIKE %s
        OR Description LIKE %s
    """, (f"%{query}%", f"%{query}%"))

    results = cursor.fetchall()
    connection.close()

    return render_template("search_results.html.jinja",
                           query=query,
                           results=results)

@app.route("/browse")
def browse():
    connection = connect_db()

    cursor = connection.cursor()
    
    cursor.execute("SELECT * FROM `Product` ")

    result = cursor.fetchall()

    connection.close()

    return render_template("browse.html.jinja", products = result)


@app.route("/product/<product_id>")
def product_page(product_id):

    connection = connect_db()
    cursor = connection.cursor()
    
    cursor.execute("SELECT * FROM `Product` WHERE `ID` = %s", ( product_id) )


    result = cursor.fetchone()

    cursor.execute("""
      SELECT * FROM Reviews 
      JOIN User ON User.ID = Reviews.UserID
      WHERE ProductID = %s
      """, (product_id)) 
    
    reviews = cursor.fetchall()
    
    connection.close()
    
    average_rating = sum(review["Ratings"] for review in reviews) / len(reviews) if reviews else 0
    
    
    if result is None:
        abort(404)

    return render_template("product.html.jinja", product=result, reviews=reviews, average_rating=average_rating)

@app.route("/product/<product_id>/add_to_cart", methods=["POST"])
@login_required
def add_to_cart(product_id):

    quantity = request.form["quantity"]


    connection = connect_db()

    cursor = connection.cursor()

    cursor.execute("INSERT INTO `Cart` (`Quantity`, `ProductID`, `UserID`) VALUES (%s, %s, %s)" \
    "ON DUPLICATE KEY UPDATE" \
    "`Quantity` = `Quantity` + %s", (quantity, product_id, current_user.id, quantity))

    result = cursor.fetchone()
    
    connection.close()


    return redirect('/cart')

@app.route("/product/<product_id>/reviews", methods=["POST"])
@login_required
def add_review(product_id):
    #get input vale from form 
    rating = request.form["rating"]
    comment = request.form["comment"]
   
   
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
      INSERT INTO Reviews
             (Ratings, Comments, UserID, ProductID)
       VALUES
            (%s,%s,%s,%s)
      """,(rating,comment,current_user.id,product_id))
    

    connection.close()

    return redirect(f"/product/{product_id}")



@app.route("/login", methods=["POST","GET"])
def login_page():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']


        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM `User`  WHERE `Email` = %s", (email))
        result = cursor.fetchone()
        connection.close()

        if result is None:
            flash("No user found. The email address and/or password you entered are invalid.")
        elif password != result["Password"]:
            flash("Incorrect Password")
        else:
            login_user(User(result))
            
            if "has_seen_greeting"  not in session:
                session["has_seen_greeting"] = False
            
            
            return redirect("/browse")

    return render_template("login.html.jinja")


@app.route("/register", methods=["POST", "GET"])
def register_page():

    if request.method == "POST":
        name = request.form["full_name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        address = request.form["address"]
        
        if password != confirm_password:
            flash("Passwords do not match")
        elif len(password) < 8:
            flash("Password is too short")
        else:
            connection = connect_db()

            cursor = connection.cursor()
            try:
                cursor.execute("""
                    INSERT INTO `User` (`Name`, `Email`, `Password`,  `Address`)
                    VALUES (%s, %s, %s, %s)
                """, (name, email, password, address))
                connection.close()
            except pymysql.err.IntegrityError:
                flash("Email is already in use")
                connection.close()
            else:
                return redirect("/login")


    return render_template("register.html.jinja")


@app.route("/logout")
@login_required
def logout():
    session.pop("has_seen_greeting", None)
    logout_user()
    flash("You have been Logged Out")

    return redirect("/")



@app.route("/cart")
@login_required
def cart():
    connection = connect_db()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM `Cart`
        JOIN `Product` ON `Product`.`ID` = `Cart`. `ProductID`
        WHERE `UserID` = %s;
""", (current_user.id))
    
    results = cursor.fetchall()
        
    connection.close()

    subtotal = sum(
        item["Price"] * item["Quantity"]
        for item in results
    )

        
    return render_template("cart.html.jinja", cart=results, subtotal=subtotal)

@app.route("/cart/<product_id>/update_quantity", methods=["POST"])
@login_required
def update_cart(product_id):
    new_quantity = request.form['quantity']

    connection = connect_db() 
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE `Cart` 
        SET `Quantity` = %s
        WHERE `ProductID` = %s AND `UserID` = %s
        
""", (new_quantity, product_id, current_user.id ))
    
    connection.close()
    return redirect('/cart')

@app.route("/cart/<product_id>/delete", methods=["POST"])
@login_required
def delete_from_cart(product_id):
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM `Cart`
        WHERE `ProductID` = %s AND `UserID` = %s
    """, (product_id, current_user.id))

    connection.close()
    return redirect("/cart")

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():

    connection = connect_db()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM `Cart`
        JOIN `Product` ON `Product`.`ID` = `Cart`.`ProductID`
        WHERE `UserID` = %s;
""", (current_user.id))
    
    results = cursor.fetchall()
    
    subtotal = sum(
        item["Price"] * item["Quantity"]
        for item in results
    )

    if request.method == "POST":
        # Create the sale in the database
        cursor.execute("INSERT INTO `Sale` (`UserID`) VALUES (%s)", (current_user.id, ))
        sale = cursor.lastrowid
        for item in results:
            cursor.execute("""INSERT INTO `SaleCart` (`SaleID`, `ProductID`, `Quantity`)
                              VALUES (%s, %s, %s)""", (sale, item['ProductID'], item['Quantity']))
        # Store products bought
        # empty cart
        cursor.execute("DELETE FROM `Cart` WHERE `UserID` = %s", (current_user.id,))
        # thank you screen
        #TODO: Make thank you page _ route
        return redirect("/thank-you")
        
    connection.close()

    return render_template("checkout.html.jinja", cart=results, subtotal=subtotal)

@app.route("/thank-you")
def thank_you():
    return render_template("thank-you.html.jinja")

@app.route("/orders")
def orders():
    connection = connect_db()
    cursor = connection.cursor()
    
    cursor.execute("""
        SELECT 
            `Sale`.`ID`,
            `Sale`.`TimeStamp`,
            SUM(`SaleCart`.`Quantity`) AS 'Quantity',
            SUM(`SaleCart`.`Quantity` * `Product`.`Price`) AS 'Total'
        FROM `Sale`
        JOIN `SaleCart` ON `SaleCart`.`SaleID` = `Sale`.`ID`
        JOIN `Product` ON `Product`.`ID` = `SaleCart`.`ProductID`
        WHERE `UserID` = %s
        GROUP BY `Sale`.`ID`; 
    """, (current_user.id))
    
    results = cursor.fetchall()


    connection.close()

    return render_template("orders.html.jinja", order=results)