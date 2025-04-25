from flask import (
    Flask,
    request,
    render_template,
    url_for,
    flash,
    get_flashed_messages,
    jsonify,
    session,
    redirect,
    send_file,
    Response,
)
import matplotlib.ticker as ticker
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv
import os
import matplotlib

matplotlib.use("Agg")
import io
from werkzeug.security import generate_password_hash, check_password_hash
import pymongo
import base64
import logging
from functools import wraps
import secrets
import smtplib
import random
from io import StringIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta


# FUNCTION DEFINING THE LOGIN REQUIRED FOR SOME ROUTES
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("Please login to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


# LOADING ENVIRONMENT VARIABLE
load_dotenv()

# INITIALISE THE FLASK APPLICATION
app = Flask(__name__)

# SET THE SECREAT KEY
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(16)

# LOG CONFIGRATION
base_path = os.getenv("BASE_PATH")
log_file = os.path.join(base_path, "AllLog", "ApplicationLog.log")
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(name)s — %(funcName)s — Line: %(lineno)d — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# DATABASE CONNECTION
try:
    Client = pymongo.MongoClient(os.getenv("mongo_url"))
    # CREATE A DATABASE
    mydb = Client["Library"]
    # CREATE A COLLECTION IN THE DATABASE FOR STUDENT
    lib_coll = mydb["Users"]
    # CREATE A COLLECTION IN THE DATABASE FOR BOOKS
    book_coll = mydb["Books"]

except Exception as e:
    logging.error("Error In DataBase Connection : {e}")


# LOGIN ROUTE
@app.route("/", methods=["POST", "GET"])
def login():
    session.clear()
    if request.method == "POST":
        # FETCH ALL THE DATA FROM THE LOGIN FORM
        roll_number = request.form.get("roll_number").strip()
        roll_number = roll_number.upper()
        password = request.form.get("password").strip()

        # CHECK IF USER HAS FILLED INVALID INPUTS
        if len(roll_number) == 0 or len(password) == 0:
            logging.info("Invalid User Details")
            flash("Invalid Details !", "warning")
            return render_template("index.html")

        # CHECK THE ROLL_NUMBER AND PASSWORD IS CORRECT ??
        try:
            user = lib_coll.find_one({"roll_number": roll_number})
        except Exception as e:
            logging.error("Error In Finding USer For Login : {e}")
        if user:
            # CHECK PASSWORD IS CORRECT OR NOT
            if check_password_hash(user["password"], password):
                # SESSION ME USER KE DETAILS KO SAVE KAR DO
                session["user"] = {
                    "roll_number": user["roll_number"],
                    "name": user.get("name", ""),
                    "email":user.get("email",""),
                }
                # SHOW FLASH MESSAGE
                flash("Login Successfully !", "success")
                # CHECK USER IS STUDENT OR ADMIN
                if user["type"] == "admin":
                    # ADMIN WALA DASH BOARD PAR LE JAO
                    logging.info(
                        f"Admin Login Successfully Name : {user['name']} Id : {str(user['_id'])}"
                    )
                    return redirect(url_for("adminDash"))
                else:
                    # STUDENT  WALE DASHBOARD PAR LE JAO
                    return redirect(url_for("studentDash"))
            else:
                # IF PASSWORD IS INCORRECT
                logging.warning("Incorrct Password")
                flash("Incorrect Password !", "info")
        else:
            # IF EMAIL ID IS INVALID
            logging.warning("Incorrect Roll No")
            flash("Incorrect Roll No !", "info")
        return render_template("index.html")
    # IF REQUEST IS NOT A POST METHOD
    return render_template("index.html")


# REGISTER ROUTE
@app.route("/register", methods=["POST", "GET"])
def register():
    logging.info("Register Page Fetched ")
    if request.method == "POST":
        # FETCH ALL THE DETIALS FROM THE REQUEST FORM
        name = request.form.get("name", "").strip()
        roll_number = request.form.get("roll_number", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        course = request.form.get("course", "").strip()
        profile_photo = request.files.get("profile_photo")

        # CHECK IF USER FILLED INVLID INPUT
        if not all([name, roll_number, email, password, course]):
            logging.info("User filled invalid input")
            flash("You have filled invalid details", "danger")
            return render_template("register.html")

        # CHECK IF ROLL NUMBER ALREADY EXIST
        user = lib_coll.find_one({"roll_number": roll_number})
        if user:
            flash(f"Roll No : {roll_number} Is Already Registered", "info")
            logging.warning(f"Roll No Is Already Registered!")
            return redirect(url_for("login"))
        # CONVERT THE PROFILE IMAGE INTO BYTEIO BUFFER
        photo_bytes = io.BytesIO(profile_photo.read())
        # SAVE THE DATA INTO THE DATABASE
        data = {
            "name": name.upper(),
            "roll_number": roll_number.upper(),
            "course": course.upper(),
            "password": generate_password_hash(password),
            "email": email.lower(),
            "type": "student",
            "fine": 0,
            "profile_image": photo_bytes.getvalue(),
            "cart": [],
            "totalBookIssue": 0,
        }
        try:
            updatedData = lib_coll.insert_one(data)
            flash("Student Register Successfully ! ", "success")
            logging.info(
                f"Student Is Registered Successfully : {updatedData.inserted_id}"
            )
            return redirect(url_for("login"))
        except Exception as e:
            flash("Something Went Wrong !", "danger")
            logging.error(f"Error Occured In Registering Student : {e}")
            return render_template("register.html")

    else:
        return render_template("register.html")


# FORGOT PASSWORD ROUTE
@app.route("/forgot", methods=["POST", "GET"])
def forgot():
    if request.method == "POST":
        # FETCH THE STEP FROM THE FORM
        step = request.form.get("step")
        if step == "1":
            roll_number = request.form.get("roll_number").strip()
            email = request.form.get("email").strip()
            if not all([roll_number, email]):
                flash("Invalid Email Or Roll Number !", "warning")
                logging.info("Invalid Roll Number Or Email!")
                return render_template("forgot.html")
            else:
                roll_number = roll_number.upper()
                email = email.lower()
            # CHECK CORRECT ROLL NUMBER OR EMAIL OR NOT??
            user = lib_coll.find_one({"roll_number": roll_number})
            if user:
                if user["email"] == email:
                    try:
                        if sendMail(email, roll_number):
                            flash(
                                f"OTP sent to your registered email: {email}", "success"
                            )
                            session["email"] = email
                            session["roll_number"] = roll_number
                            return redirect(url_for("forgot", step=2))
                        else:
                            flash(
                                "Failed to send OTP. Please try again later.", "danger"
                            )
                            return redirect(url_for("forgot"))
                    except Exception as e:
                        flash("SOMETHING WENT WRONG,PLEASE TRY AGAIN LATER", "danger")
                        logging.info(f"Something Went Wrong In Sending OTP  : {e}")
                        return redirect(url_for("forgot"))
                else:
                    flash("Invalid Email ", "danger")
                    logging.info("Invalid Email ")
                    return render_template("forgot.html")
            else:
                flash("Invalid Roll Number ", "danger")
                logging.info(f"Roll No : {roll_number}")
                return render_template("forgot.html")

        elif step == "2":
            # FETCH OTP FROM THE REQUEST FORM
            otp = request.form.get("otp").strip()
            email = session.get("email").strip()
            roll_number = session.get("roll_number").strip()

            if len(otp) == 0:
                logging.info("OTP Can Not Be Blank")
                flash("OTP cannot be left blank", "warning")
                return redirect(url_for("forgot", step=2))
            # VERIFY OTP
            if verify_otp(email, roll_number, otp):
                flash(f"OTP Verified Successfully", "success")
                logging.info(f"OTP Verified Successfully")
                return redirect(url_for("forgot", step=3))
            else:
                flash(f"Incorrect OTP,Please Try Again", "warning")
                logging.info(f"Incorrct OTP : {otp}")
                return redirect(url_for("forgot", step=2))
        elif step == "3":
            password = request.form.get("new_password").strip()
            confirm_password = request.form.get("confirm_password").strip()
            roll_number = session.get("roll_number")

            if not all([password, confirm_password]):
                logging.info("Password cannot be left blank")
                flash("Both password fields are required.", "warning")
                return redirect(url_for("forgot", step=3))
            if password != confirm_password:
                logging.info("Passwords do not match.")
                flash("Passwords do not match.", "warning")
                return redirect(url_for("forgot", step=3))

            hashed_password = generate_password_hash(password)

            # UPDATE THE PASSWORD IN THE DATABASE
            try:
                lib_coll.update_one(
                    {"roll_number": roll_number},
                    {"$set": {"password": hashed_password}},
                )
                flash("Password updated successfully!", "success")
                logging.info(f"Password updated for {roll_number}")
                # Clean up session data
                session.pop("roll_number", None)
                session.pop("email", None)
                return redirect(url_for("login"))
            except Exception as e:
                logging.danger(f"Error updating password for {roll_number}: {e}")
                flash("Failed to update password. Try again later.", "danger")
                return redirect(url_for("forgot", step=3))
    else:
        # IF THE REQUEST METHOD IS GET
        step = request.args.get("step", "1")
        return render_template("forgot.html", step=step)


# VERIFY OTP FUNCTION
def verify_otp(email, roll_number, otp):
    user = lib_coll.find_one({"roll_number": roll_number})

    if not user:
        return False

    if user.get("email") != email:
        return False

    stored_otp = user.get("otp")
    otp_created = user.get("otp_created")

    if not stored_otp or not otp_created:
        return False

    # MATCH THE OTP
    if stored_otp != otp:
        return False

    # CHECK IF OTP IS EXPIRED VALID FOR 2 MINUTES ?
    if datetime.utcnow() - otp_created > timedelta(minutes=2):
        return False
    # CLEAR THE OTP AFTER SUCCESSFUL VERIFICATION
    lib_coll.update_one(
        {"roll_number": roll_number}, {"$unset": {"otp": "", "otp_created": ""}}
    )
    return True


# SEND OTP FUNCTION
def sendMail(email, roll_number):
    logging.info("Send Mail Function Called")

    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("EMAIL_APP_PASS")

    otp = str(random.randint(1000, 9999))
    otp_validity_minutes = 2  # OTP expires in 2 minutes

    # Setup MIME
    message = MIMEMultipart()
    message["From"] = f"DHSGU-Library <{sender_email}>"
    message["To"] = email
    message["Subject"] = "OTP for Password Reset - DHSGU Library"

    # Email Body (Professional & Clear)
    body = f"""
Dear Student,

You have requested to reset your password for the DHSGU Library Portal.

Your One-Time Password (OTP) is: **{otp}**

⚠️ Please note: This OTP is valid for only {otp_validity_minutes} minutes. Do not share it with anyone for security reasons.

If you did not initiate this request, please ignore this email or contact library support.

Regards,  
DHSGU Library Team
"""
    message.attach(MIMEText(body, "plain"))

    # Send Email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email, message.as_string())

        # Save OTP with timestamp
        lib_coll.find_one_and_update(
            {"roll_number": roll_number},
            {"$set": {"otp": otp, "otp_created": datetime.utcnow()}},
        )

        logging.info(f"OTP sent to {email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email to {email}: {e}")
        return False


# STUDENT DASHBOARD ROUTE
@app.route("/studentDash", methods=["POST", "GET"])
@login_required
def studentDash(): 
    user = session["user"]
    roll_number = user["roll_number"]
    try:
        data = lib_coll.find_one({"roll_number": roll_number})
        books = list(book_coll.find({"borrowers.roll_number": roll_number}))
    except Exception as e:
        logging.error(f"Error Occured In Finding Books And Student : {e}")
        flash("Something Went Wrong", "danger")
        return redirect(url_for("login"))
    bookList = []
    if not books:
        books = []
    else:
        for book in books:
            for i in book["borrowers"]:
                if i["roll_number"] == roll_number:
                    issue_date = i["date_of_issue"]
            date_obj = datetime.strptime(issue_date, "%d-%m-%y")
            new_date = date_obj + timedelta(days=7)
            return_date = new_date.strftime("%d-%m-%y")
            bookData = {
                "name": book["name"],
                "id": book["id"],
                "writter": book["writter"],
                "subject": book["subject"],
                "issue_date": issue_date,
                "return_date": return_date,
            }
            bookList.append(bookData)
        logging.info(f"Book Data  : {bookData}")
    user = {
        "name": data["name"],
        "issuedBooks": bookList,
        "fine": data["fine"],
        "books": [],
        "total_cart_item": len(data["cart"]),
    }
    if request.method == "POST":
        submit = request.form.get("submit")

        # TO SEARCH THE BOOKS

        if submit == "search_book":
            search_by = request.form.get("search_by").strip()
            search = request.form.get("search").strip().strip()
            if search and search_by:
                try:
                    search = search.upper()
                    search_by = search_by.lower()
                    logging.info(f"Search By: {search_by}, Search Term: {search}")
                    books = list(book_coll.find({search_by: search}))
                    logging.info(f"Books Are : {books}")
                    bookList = []
                    if books:
                        for i in books:
                            try:
                                bookData = {
                                    "name": i["name"],
                                    "id": i["id"],
                                    "writter": i["writter"],
                                    "subject": i["subject"],
                                    "totalAvailable": i["available"],
                                    "totalIssued": i["totalborrowed"],
                                }
                                bookList.append(bookData)
                                logging.info(f"BookData : {bookData}")
                            except:
                                logging.info("Kya Ho Rha Hai Ye")

                    logging.info(f"BookList Are  : {bookList}")
                    user["searched_book"] = bookList
                    logging.info("Book Searched Successfully")
                    flash("Book Search Successfully", "success")
                    return render_template("studentDash.html", user=user)
                except Exception as e:
                    logging.error("Error Occured In SEarching Book : {e}")
                    flash("Something Went Wrong", "danger")
                    return render_template("studentDash.html", user=user)

        # TO GENRATE THE GRAPH

        elif submit == "generate_graph":
            image = None
            if request.method == "POST":
                subject = request.form.get("subject").strip()
                if subject:
                    try:
                        books = (
                            book_coll.find({"subject": subject})
                            .sort("totalborrowed", pymongo.DESCENDING)
                            .limit(10)
                        )
                    except Exception as e:
                        logging.error(f"Error Occured In Finding The Book : {e}")
                        flash("Something Went Wrong", "danger")
                        return render_template("studentDash.html", user=user)

                    # Extract titles and totalborrowed values
                    titles = []
                    counts = []
                    for book in books:
                        titles.append(book.get("name", "Untitled"))
                        counts.append(
                            int(book.get("totalborrowed", 0))
                        )  # Ensure integer

                    if not titles:
                        flash("No books found for this subject", "info")
                        return render_template("studentDash.html", user=user)

                    # Plotting the pie chart
                    plt.figure(figsize=(10, 8))
                    plt.pie(counts, labels=titles, autopct="%1.1f%%", startangle=140)
                    plt.title(f"Top 10 Issued Books in '{subject}'", fontsize=14)
                    plt.axis(
                        "equal"
                    )  # Equal aspect ratio ensures the pie chart is circular

                    # Save plot to a BytesIO buffer
                    buf = io.BytesIO()
                    plt.savefig(buf, format="png")
                    buf.seek(0)
                    image = base64.b64encode(buf.read()).decode("utf-8")
                    buf.close()
                    plt.close()

                    user["image"] = image
                    logging.info("Pie Chart Generated Successfully")
                    flash("Graph Generated Successfully", "success")
                    return render_template("studentDash.html", user=user)
                else:
                    flash("Invalid Subject", "warning")
                    logging.info("Invalid Subject")
                    return render_template("studentDash.html", user=user)

    return render_template("studentDash.html", user=user)


@app.route("/profile_imageFetch/<roll_number>")
def profile_imageFetch(roll_number):
    roll_number = roll_number.upper()
    user = lib_coll.find_one({"roll_number": roll_number})
    if user and user.get("profile_image"):
        return Response(user["profile_image"], mimetype="image/jpeg")
    return "Image not found", 404


# PROFILE ROUTE
@app.route("/profile", methods=["POST", "GET"])
@login_required
def profile():
    user = session["user"]
    roll_number = user["roll_number"].upper()

    try:
        user = lib_coll.find_one({"roll_number": roll_number})
        student = {
            "name": user["name"],
            "course": user["course"],
            "roll_number": user["roll_number"],
            "email": user["email"],
            "fine": user["fine"],
            "total_books_issued": user["totalBookIssue"],
            "total_cart_item": len(user["cart"]),
            "profile_image": url_for("profile_imageFetch", roll_number=roll_number),
        }
        logging.info(f"Student Data For Profile Is : {student}")
    except Exception as e:
        logging.error(f"Some Error Occured {e}")
        flash("Something Went Wrong", "danger")
        return redirect(url_for("studentDash"))

    return render_template("profile.html", student=student)


# ADD TO CART ROUTE
@app.route("/add_to_cart", methods=["POST", "GET"])
@login_required
def addBookToCart():
    logging.info("Add To Cart Called Successfully")
    try:
        user = session["user"]
        roll_number = user["roll_number"]
        data = request.get_json()
        bookId = data.get("book_id")
        if not bookId:
            return jsonify({"success": False, "message": "No book ID provided."}), 400

        # Check if the book is already in the student's cart
        student = lib_coll.find_one({"roll_number": roll_number})
        if bookId in student.get("cart", []):
            logging.info("Book Already Added To Cart")
            return jsonify({"success": False, "message": "Book already in cart."})

        # Find book details
        bookData = book_coll.find_one({"id": bookId})
        if not bookData:
            return jsonify({"success": False, "message": "Book not found."}), 404

        # Add the book to the student's cart
        lib_coll.find_one_and_update(
            {"roll_number": roll_number}, {"$push": {"cart": bookData["id"]}}
        )
        logging.info("Successfully Added Book To The Cart")
        return jsonify({"success": True, "message": "Book added to cart."})

    except Exception as e:
        logging.error(f"Error Adding Book To Cart: {e}")
        return jsonify({"success": False, "message": "Server error."}), 500

# DOWNLOAD BOOK ROUTE 
@app.route('/download_book', methods=['POST'])
@login_required
def download_book():
    books = {
        "ML001": {"name": "Book One", "file_path": "books/Harry-Potter-and-the-Sorcerers-Stone.pdf"},
        "C001": {"name": "Book Two", "file_path": "books/Harry-Potter-and-the-Sorcerers-Stone.pdf"},
    }
    data = request.get_json()
    book_id = data.get('book_id')

    if book_id not in books:
        return jsonify({"success": False, "message": "Book not found."}), 404

    book = books[book_id]
    file_path = book['file_path']

    # Log the file path for debugging
    print(f"File path: {file_path}")

    if not os.path.exists(file_path):
        return jsonify({"success": False, "message": "File not found."}), 404

    return send_file(file_path, as_attachment=True)

# CART ROUTE
@app.route("/cart", methods=["POST", "GET"])
@login_required
def cart():
    user = session["user"]
    roll_number = user["roll_number"]
    studentData = lib_coll.find_one({"roll_number": roll_number})
    bookIds = studentData.get("cart", [])

    # Fetch all books in one query
    books = list(book_coll.find({"id": {"$in": bookIds}}))

    # Create a simplified book list for rendering
    bookList = []
    for book in books:
        bookList.append(
            {
                "id": book["id"],
                "subject": book["subject"],
                "name": book["name"],
                "writer": book["writter"],
                "available": book["available"],
                "issued": book["totalborrowed"],
            }
        )

    if request.method == "POST":
        pass

    return render_template("cart.html", cart_books=bookList)


# REMOVE BOOK FROM CART
@app.route("/remove_book", methods=["POST", "GET"])
@login_required
def remove_book():
    if request.method == "POST":
        user = session["user"]
        roll_number = user["roll_number"]
        bookId = request.form.get("book_id")
        logging.info(f"BookID  : {bookId}")
        lib_coll.find_one_and_update(
            {"roll_number": roll_number}, {"$pull": {"cart": bookId}}
        )
        return redirect(url_for("cart"))


# ********************************** ADMIN METHODS ******************************


# ADMIN DASHBOARD ROUTE
@app.route("/adminDash", methods=["POST", "GET"])
@login_required
def adminDash():
    user = session["user"]
    user = {"name": user["name"],"email":user['email'], "searched_books": []}
    if request.method == "POST":
        submit = request.form.get("submit")
        # ********** ISSUE BOOK ***********
        if submit == "issue_book":
            roll_number = request.form.get("roll_number").strip()
            book_id = request.form.get("book_id").strip()

            if not all([roll_number, book_id]):
                logging.info("Input Value Is Whitespaces")
                flash("You Have Entered Invalid Value ", "warning")
                return redirect(url_for("adminDash"))
            try:
                roll_number = roll_number.upper()
                book_id = book_id.upper()
                student = lib_coll.find_one({"roll_number": roll_number})
                book = book_coll.find_one({"id": book_id})
            except Exception as e:
                logging.error(f"Error Occured In Finding Student & Book To Issue : {e}")
                flash("Something Went Wrong", "danger")
                return redirect(url_for("adminDash"))
            if book:
                if student:
                    if book["available"] > 0:
                        if student["totalBookIssue"] == 2:
                            logging.error(
                                "Student Have Already Issued The Max Number Of Books!"
                            )
                            flash("Max No. Of Book Issued", "warning")
                            return redirect(url_for("adminDash"))
                        else:
                            currentDate = str(datetime.today().strftime("%d-%m-%y"))
                            stData = {
                                "roll_number": roll_number,
                                "date_of_issue": currentDate,
                            }
                            try:
                                lib_coll.find_one_and_update(
                                    {"roll_number": roll_number},
                                    {"$inc": {"totalBookIssue": 1}},
                                )
                                book_coll.find_one_and_update(
                                    {"id": book_id},
                                    {
                                        "$inc": {"available": -1, "totalborrowed": 1},
                                        "$push": {"borrowers": stData},
                                    },
                                )
                                currentDateObj = datetime.strptime(currentDate, "%d-%m-%y")
                                newDateObj = currentDateObj + timedelta(days=7)
                                returnDate = newDateObj.strftime("%d-%m-%y")
                                logging.info(f"{student['email']},{book['name']},{book['subject']},{currentDate},{str(returnDate)}")
                                if sendBookIssueMail(student['email'],book['name'],book['subject'],currentDate,str(returnDate)) :
                                    logging.info(
                                        f"Book Issued Successfully,Book_ID :{book_id}, Student_Rollno :{roll_number}"
                                    )
                                    flash("Book Issued Successfully", "success")
                                    return redirect(url_for("adminDash"))
                                else:
                                    logging.error(
                                    f"Error Occured In SENDING MAIL TO THE USER"
                                )
                                flash("Something Went Wrong", "danger")
                                return redirect(url_for("adminDash"))
                            except Exception as e:
                                logging.error(
                                    f"Error Occured In UPDATING BOOK AND STUDNET TO ISSUE BOOK  : {e}"
                                )
                                flash("Something Went Wrong", "danger")
                                return redirect(url_for("adminDash"))
                    else:
                        logging.info("Book Is Out Of Stock")
                        flash("Sorry,Book Is Out Of Stock", "warning")
                        return redirect(url_for("adminDash"))
                else:
                    logging.info("Invalid Student Roll No")
                    flash("Invalid Student Roll No", "danger")
                    return redirect(url_for("adminDash"))
            else:
                logging.info("Invalid Book Id")
                flash("Invalid Book Id", "danger")
                return redirect(url_for("adminDash"))

        # ************ RETURN BOOK ***********
        elif submit == "return_book":
            roll_number = request.form.get("roll_number").strip()
            book_id = request.form.get("book_id").strip()

            if not all([roll_number, book_id]):
                logging.warning("Value As Whitespaces")
                flash("You Have Entered Invalid Input", "warning")
                return redirect(url_for("adminDash"))
            roll_number = roll_number.upper()
            book_id = book_id.upper()
            try:
                student = lib_coll.find_one({"roll_number": roll_number})
                book = book_coll.find_one({"id": book_id})
            except Exception as e:
                logging.error(
                    "Error Occured During Finding Student & Book For Retun Book"
                )
                flash("Something Went Wrong", "danger")
                return redirect(url_for("adminDash"))
            if book:
                if student:
                    flag = 0
                    borrowers = book["borrowers"]
                    for i in borrowers:
                        if i["roll_number"] == roll_number:
                            flag = i
                            borrowers.remove(i)
                            break
                    if flag == 0:
                        logging.warning(
                            f"Student With Roll : {roll_number} Has Not Issued Book With Book_id :{book_id}"
                        )
                        flash("Given Book Id Is Not Issued By Student", "warning")
                        return redirect(url_for("adminDash"))
                    currentDate = str(datetime.today().strftime("%d-%m-%y"))
                    issueDate = flag["date_of_issue"]
                    # CONVERT STRING DATE TO DATETIME OBJECTS
                    current_date_obj = datetime.strptime(currentDate, "%d-%m-%y")
                    issue_date_obj = datetime.strptime(issueDate, "%d-%m-%y")

                    # CALCULATE THE DIFFERENCE IN DAYS
                    total_days = (current_date_obj - issue_date_obj).days
                    fine = 0
                    if total_days > 7:
                        fine = (total_days - 7) * 5
                    # UPDATE INTO THE DATABASE
                    try:
                        book_coll.find_one_and_update(
                            {"id": book_id},
                            {
                                "$inc": {"available": 1},
                                "$set": {"borrowers": borrowers},
                            },
                        )
                        lib_coll.find_one_and_update(
                            {"roll_number": roll_number},
                            {"$inc": {"totalBookIssue": -1, "fine": fine}},
                        )
                        logging.info("Book Returned Successfully")
                        flash(f"Book Retured Successfully Fine:{fine}", "success")
                        return redirect(url_for("adminDash"))
                    except Exception as e:
                        logging.error(
                            "Error In Updating Student & Books On Returning Book  : {e}"
                        )
                        flash("Something Went Wrong", "danger")
                        return redirect(url_for("adminDash"))
                else:
                    logging.warning("Invalid Roll No")
                    flash("Invalid Roll No ", "danger")
                    return redirect(url_for("adminDash"))
            else:
                logging.warning("Invalid Book Id")
                flash("Invalid Book Id", "danger")
                return redirect(url_for("adminDash"))

        # ************ SEARCH BOOK *************
        elif submit == "search_book":
            search_by = request.form.get("search_by").strip()
            search = request.form.get("search").strip()
            if not all([search_by, search]):
                logging.warning("Value Entered Is Whitespace For Searching Books")
                flash("You Have Entered Invalid Details", "warning")
                return redirect(url_for("adminDash"))
            search = search.upper()
            try:
                books = book_coll.find({search_by: search})
                try:
                    books = list(books)
                except Exception as e:
                    logging.error("Kuchh To Garbar Hai Bhai : {e}")
                    flash("Something Went Wrong", "danger")
                    return redirect("adminDash")
                for book in books:
                    book.pop("_id", None)
                user["searched_books"] = books
                logging.info(f"Book Searched Successfully,Books  : {books[0]}")
                flash("Book Search Successfully", "success")
                return render_template("adminDash.html", user=user)
            except Exception as e:
                logging.error(f"Error In Searching Book : {e}")
                flash("Something Went Wrong", "danger")
                return redirect(url_for("adminDash"))

        # ************ VISUALISE GRAPH **************
        elif submit == "generate_graph":
            image = None
            if request.method == "POST":
                subject = request.form.get("subject").strip()
                if subject:
                    try:
                        books = (
                            book_coll.find({"subject": subject})
                            .sort("totalborrowed", pymongo.DESCENDING)
                            .limit(10)
                        )
                    except Exception as e:
                        logging.error(f"Error Occured In Finding The Book : {e}")
                        flash("Something Went Wrong", "danger")
                        return render_template("adminDash.html", user=user)

                    # Extract titles and totalborrowed values
                    titles = []
                    counts = []
                    for book in books:
                        titles.append(book.get("name", "Untitled"))
                        counts.append(
                            int(book.get("totalborrowed", 0))
                        )  # Ensure integer

                    if not titles:
                        flash("No books found for this subject", "info")
                        return render_template("adminDash.html", user=user)

                    # Calculate percentages for the legend
                    total = sum(counts)
                    percentages = [(count / total) * 100 for count in counts]
                    legend_labels = [
                        f"{titles[i]} - {percentages[i]:.1f}%"
                        for i in range(len(titles))
                    ]

                    # Plotting the pie chart
                    plt.figure(figsize=(10, 8))
                    plt.pie(counts, startangle=140)
                    plt.title(f"Top 10 Issued Books in '{subject}'", fontsize=14)
                    plt.axis("equal")

                    # Add legend below the chart
                    plt.legend(
                        legend_labels,
                        loc="lower center",
                        bbox_to_anchor=(0.5, -0.1),
                        ncol=2,
                        fontsize="small",
                    )

                    plt.tight_layout()

                    # Save plot to a BytesIO buffer
                    buf = io.BytesIO()
                    plt.savefig(buf, format="png", bbox_inches="tight")
                    buf.seek(0)
                    image = base64.b64encode(buf.read()).decode("utf-8")
                    buf.close()
                    plt.close()

                    user["image"] = image
                    logging.info("Pie Chart with Legend Generated Successfully")
                    flash("Graph Generated Successfully", "success")
                    return render_template("adminDash.html", user=user)
                else:
                    flash("Invalid Subject", "warning")
                    logging.info("Invalid Subject")
                    return render_template("adminDash.html", user=user)
    return render_template("adminDash.html", user=user)

def sendBookIssueMail(email,bookName,bookSubject,date_of_issue,return_date):
    logging.info("Send Mail Function Called")

    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("EMAIL_APP_PASS")
    # Setup MIME
    message = MIMEMultipart()
    message["From"] = f"DHSGU-Library <{sender_email}>"
    message["To"] = email
    message["Subject"] = "📚 Book Issued Successfully – Library Notification | DHSGU Library"

    # Email Body (Professional & Clear)
    body = f"""
Subject: 

Dear Student,

We’re happy to let you know that a new book has been issued to your library account. Below are the details of your issued book:

─────────────────────────────  
📖 **Book Name:** *{bookName}*  
📘 **Subject:** *{bookSubject}*  
🗓️ **Issued On:** *{date_of_issue}*  
📅 **Due On:** *{return_date}*  
─────────────────────────────  

🔔 **Kind Reminder:**  
Please ensure that the book is returned on or before the due date to avoid any late charges. Handle it responsibly and return it in good condition so others can enjoy it too.

If you have any questions or need help, feel free to reach out. We’re here to assist you!

📞 **For Any Query:**  
**THAKUR SATYAM**  
📍 Ranganathan Library  
📱 +91 91172 56040  

Warm regards,  
**📚 DHSGU Library Team**
"""

    message.attach(MIMEText(body, "plain"))

    # Send Email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email, message.as_string())

        logging.info(f"Mail Sent To The Student")
        return True
    except Exception as e:
        logging.error(f"Failed to send email to {email}: {e}")
        return False



# ADD BOOK ROUTE
@app.route("/add_book", methods=["POST", "GET"])
@login_required
def add_book():
    if request.method == "POST":
        name = request.form.get("name").strip()
        id = request.form.get("id").strip()
        writter = request.form.get("writter").strip()
        subject = request.form.get("subject").strip()
        available = int(request.form.get("available").strip())

        if not all([name, id, writter, subject, available]):
            flash("You Have Entered Invalid Data", "warning")
            logging.error("Invalid Data Entered: Value As WhiteSpaces")
            return redirect(url_for("adminDash"))
        data = {
            "name": name.upper(),
            "id": id.upper(),
            "writter": writter.upper(),
            "subject": subject.upper(),
            "available": available,
            "borrowers": [],
            "totalborrowed": 0,
        }
        try:
            book_coll.insert_one(data)
            logging.info("Book Added Successfully")
            flash("Book Added Successfully!", "success")
            return redirect(url_for("adminDash"))
        except Exception as e:
            logging.error(f"Error Occured During Adding Book : {e}")
            flash("Something Went Wrong In Adding Book", "danger")
            return redirect(url_for("adminDash"))
    return redirect(url_for("adminDash"))


# LOG OUT ROUTE
@app.route("/logout", methods=["POST", "GET"])
@login_required
def logout():
    session.clear()
    flash("Logout Successfully", "success")
    return redirect(url_for("login"))


# RUN THE SERVER
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.getenv("PORT"))
