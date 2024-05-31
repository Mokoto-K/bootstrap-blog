# In python we have a package for everything....
# even from python import python

from flask_login import LoginManager, login_user, UserMixin, logout_user, current_user, login_required
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, SubmitField, EmailField
from flask_ckeditor import CKEditor, CKEditorField
from wtforms.validators import DataRequired
from sqlalchemy import ForeignKey, Integer
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap5
from flask_gravatar import Gravatar
from flask_wtf import FlaskForm
from functools import wraps
import datetime as dt
import smtplib
import os



# Email address that contact requests are sent too and password for access to this app
EMAIL = os.environ.get("EMAIL")
PWORD = os.environ.get("EMAIL_PWORD")


class Base(DeclarativeBase):
    pass


app = Flask(__name__)
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
# Must install older version of flask for this gravatar to work
gravatar = Gravatar(app, size=50)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DB_URI", "sqlite:///blog.db")
app.config["SECRET_KEY"] = os.environ.get("FLASK_KEY")

db.init_app(app)
login_manager.init_app(app)

bootstrap = Bootstrap5(app)
ckeditor = CKEditor(app)


# ----------------------------- Databases ----------------------------------
# TODO: Recreate all databases with more specific column values and variables i.e urls, ints, etc
# creates database  for users
class User(db.Model, UserMixin):
    __tablename__ = "user_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    username: Mapped[str] = mapped_column(nullable=False)
    password: Mapped[str] = mapped_column(nullable=False)

    # Creates relationship with the authors of blogposts
    posts = relationship("Posts", back_populates='author')
    comments = relationship("Comment", back_populates="comment_author")


# Create database for post
class Posts(db.Model):
    __tablename__ = "posts_table"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Creates the forgeinkey to link Users and posts tables together
    author_id: Mapped[int] = mapped_column(ForeignKey("user_table.id"))

    # Creates relationsihp with the blogposts and authors
    author = relationship("User", back_populates="posts")

    #Creates relationship with blogposts and comments
    comments = relationship("Comment", back_populates="parent_post")


    title: Mapped[str] = mapped_column(nullable=False)
    subtitle: Mapped[str] = mapped_column(nullable=False)
    date: Mapped[str] = mapped_column(nullable=False)
    body: Mapped[str] = mapped_column(nullable=False)
    img_url: Mapped[str] = mapped_column(nullable=False)


# Creates database for comments
class Comment(db.Model):
    __tablename__ = "comment_table"
    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(nullable=False)

    #Creat relationship with each user and thier comments and each post and it's comments
    parent_post = relationship("Posts", back_populates="comments")
    comment_author = relationship("User", back_populates="comments")

    # Creates relationships between Comments and user tables and comments and posts tables
    author_id: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    post_id: Mapped[int] = mapped_column(ForeignKey("posts_table.id"))


# Creates all database
with app.app_context():
    db.create_all()

# ------------------------- FORMS ----------------------------------------


# Register
# TODO Add email and password validators to this form
class RegisterForm(FlaskForm):
    email = EmailField(name='email', validators=[DataRequired()])
    username = StringField(name='username', validators=[DataRequired()])
    password = StringField(name="password", validators=[DataRequired()])
    submit = SubmitField(name='submit', validators=[DataRequired()])


# Login
# TODO: ADD a confirm password field
class LoginForm(FlaskForm):
    email = EmailField(name='email', validators=[DataRequired()])
    password = StringField(name="password", validators=[DataRequired()])
    submit = SubmitField(name="submit", validators=[DataRequired()])


# Create new post
# TODO: Add proper validators for this form, specify exactly what is and not is allowed
class NewPostForm(FlaskForm):
    title = StringField(name="title", validators=[DataRequired()])
    subtitle = StringField(name="subtitle", validators=[DataRequired()])
    author = StringField(name="author", validators=[DataRequired()])
    image = StringField(name="image", validators=[DataRequired()])
    body = CKEditorField(name="body", validators=[DataRequired()])
    submit = SubmitField(name="Submit", validators=[DataRequired()])


class CommentForm(FlaskForm):
    comment = CKEditorField(name="comment", validators=[DataRequired()])
    submit = SubmitField(name="Submit", validators=[DataRequired()])
# ------------------------ Home, about me, contact --------------------------


@app.route("/")
def home():
    all_posts = db.session.execute(db.select(Posts)).scalars().all()
    year = str(dt.date.today()).split("-")[0]
    return render_template("index.html", posts=all_posts, current_year=year)


# TODO: Fix about me, make it more personal change image
@app.route("/about")
def about():
    return render_template("about.html")


# TODO: Update text and image for page
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        info = request.form
        send_contact_email(info["name"], info["email"], info["phone"], info["message"])
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", msg_sent=False)


# Auto email me if someone fills out my contact form
def send_contact_email(name, email, phone, message):
    # Message that will be emailed to me if someone submits a contact form
    message = (f"Subject: New Contact Message \n\n"
               f"Name: {name}\n"
               f"Email: {email}\n"
               f"Phone: {phone}\n"
               f"Message: {message})")
    # Email
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(EMAIL, PWORD)
        connection.sendmail(EMAIL, EMAIL, msg=message)


# ------------------------- Everything to do with posts------------------------
# VERY TRICKY piece of code, a decorator to grant admin privliages, not very intuitive or straight forward
# You are essentially double wrapping endpoints that need to be restricted with a decorator in
# a decorator.... i am convinced there is a better way than this.
# TODO: Loook to find an optimised version of creating this decorator
# TODO: perhaps redirect users elsewhere instead of showing them forbbidden... up to me really.
def admin_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.id != 1:
            abort(403)
        else:
            return func(*args, **kwargs)
    return wrapper

# TODO: COMMENTS dont clear out of the textbox after they are posted
# Loads the "post" page with the clicked on blog post from the home page
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def post(post_id):
    form = CommentForm()
    current_post = db.session.execute(db.select(Posts).where(Posts.id == post_id)).scalar()
    if form.validate_on_submit():
        # Targets none logged in users and prevents them from commenting.
        if current_user.is_anonymous:
            flash("You must be logged in to make comments")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=form.data.get('comment'),
            author_id=current_user.id,
            post_id=post_id
        )
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=current_post, form=form)


# TODO: There is probbly mistakes here so feel free to comb through
# Make a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def new_post():
    """Creates a new post"""
    heading = "New Post"
    form = NewPostForm()
    if form.validate_on_submit():
        add_post = Posts(
            title=request.form.get("title"),
            date=dt.date.today().strftime("%B %-d, %Y"),
            body=request.form.get("body"),
            # Normally just author as a string but needed to be an obj once we linked databases
            author=current_user,
            img_url=request.form.get("image"),
            subtitle=request.form.get("subtitle"))

        db.session.add(add_post)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("make-post.html", form=form, heading=heading)


# TODO: MAKE THE POST A CLASS SO THAT I CAN JUST CALL THE POST.ATTRIBUTE TO PREPOPULATE THE FORM


@app.route("/edit-post/<int:id>", methods=["GET", "POST"])
@admin_only
def edit_post(id):
    """Edits a post"""
    heading = "Edit Post"
    get_post = db.session.execute(db.select(Posts).where(Posts.id == id)).scalar()
    form = NewPostForm(
        title=get_post.title,
        subtitle=get_post.subtitle,
        author=get_post.author,
        image=get_post.img_url,
        body=get_post.body
    )
    # TODO: Write a function to that when we want to validate a from from edit or create new
    # TODO: we can just send the form to that function instead of reapeating code
    if form.validate_on_submit():
        with app.app_context():
            get_post = db.session.execute(db.select(Posts).where(Posts.id == id)).scalar()
            get_post.title = request.form.get("title")
            get_post.body = request.form.get("body")
            get_post.author = request.form.get("author")
            get_post.img_url = request.form.get("image")
            get_post.subtitle = request.form.get("subtitle")
            db.session.commit()
        return redirect(url_for("post", post_id=id))
    return render_template("make-post.html", form=form, heading=heading)


# TODO: Change the delete for an X to an image, this has to be done on the index
@app.route("/delete/<int:id>")
@admin_only
def delete_post(id):
    get_post = Posts.query.get(id)
    db.session.delete(get_post)
    db.session.commit()
    return redirect(url_for("home"))


# --------------------Register, login and logout users-----------------------------
# TODO: Figure out why usermixin causess lint when initializing User class... besides the obvious reason
@app.route("/register", methods=["GET", "POST"])
def register_user():
    form = RegisterForm()

    # checks if email already exists
    if db.session.scalar(db.select(User).where(User.email == form.email.data)):
        flash("Email already registered, login instead")
        return redirect(url_for("login"))

    if form.validate_on_submit():
        password = request.form.get('password')
        user = User(
          email=request.form.get('email'),
          username=request.form.get('username'),
          password=generate_password_hash(password, "pbkdf2", len(password))
          )

        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("home"))
    return render_template("register.html", form=form)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

# TODO: Implement sanitation on inputs
# TODO: Implement html changes for if a user is logged in already and they go to log in page
# TODO: Implement 'next' to avoid open redirect attacks, not needed for development, but needed for production
@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(db.select(User).where(User.email == form.email.data))
        if user is None:
            flash("User does not exist")
            return redirect(url_for("login"))
        elif not check_password_hash(user.password, form.password.data):
            flash("Invalid password")
            return redirect(url_for("login"))
        login_user(user)
        return redirect(url_for("home"))
    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=False)

# TODO: Change all the dict[title] style calls in the html to post.title or whatever it is meant to be
# TODO: There are endless problems with text all throughout the site, wrong labels, bad grammar,etc
# TODO: BIG BUG with deleteing post, the id's dont update, their eventually stuff starts to crash when typing in addresses.
# TODO: Start a custom css file