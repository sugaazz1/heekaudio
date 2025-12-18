from flask import Flask, render_template, request, flash, redirect, abort
from flask_login import LoginManager, login_user, logout_user, login_required
from flask import flash
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

    connection.close()
    
    if result is None:
        abort(404)

    return render_template("product.html.jinja", product=result)


#@app.route("cart/<product_id>", methods=["POST"])
#def add_to_cart(product_id):

    #return


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

    logout_user()
    flash("You have been Logged Out")

    return redirect("/")