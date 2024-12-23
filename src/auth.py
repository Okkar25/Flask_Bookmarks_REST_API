from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from src.constants.http_status_codes import (
    HTTP_400_BAD_REQUEST,
    HTTP_409_CONFLICT,
    HTTP_201_CREATED,
    HTTP_401_UNAUTHORIZED,
    HTTP_200_OK,
)
import validators
from src.database import db, User
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jti,
    get_jwt,
)


auth = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

revoked_tokens = set()  # In-memory token blacklist


# @auth.route("/register", methods=["POST"])
@auth.post("/register")
def register():
    username = request.json["username"]  # request.form.get()
    email = request.json["email"]
    password = request.json["password"]

    # data validation
    if len(password) < 6:
        return (
            jsonify({"error": "Password must be longer than 6 characters."}),
            HTTP_400_BAD_REQUEST,
        )

    if len(username) < 3:
        return (
            jsonify({"error": "Username must be longer than 3 characters."}),
            HTTP_400_BAD_REQUEST,
        )

    if not username.isalnum() or " " in username:
        return (
            jsonify({"error": "username should be alphanumeric with no spaces"}),
            HTTP_400_BAD_REQUEST,
        )

    # use validators package
    if not validators.email(email):
        return (
            jsonify({"error": "You must enter a valid email address."}),
            HTTP_400_BAD_REQUEST,
        )

    if User.query.filter_by(email=email).first() is not None:
        return jsonify({"error": "This email is taken"}), HTTP_409_CONFLICT

    if User.query.filter_by(username=username).first() is not None:
        return jsonify({"error": "This username is taken"}), HTTP_409_CONFLICT

    pwd_hash = generate_password_hash(password)

    user = User(username=username, email=email, password=pwd_hash)
    db.session.add(user)
    db.session.commit()

    return (
        jsonify(
            {"message": "User created", "user": {"username": username, "email": email}}
        ),
        HTTP_201_CREATED,
    )


@auth.post("/login")
def login():
    email = request.json.get("email", "")
    password = request.json.get("password", "")

    user = User.query.filter_by(email=email).first()

    if user:
        is_correct_pwd = check_password_hash(user.password, password)

        if is_correct_pwd:
            # identity needs to be string # str(user.id) # get_jwt_identity()
            access = create_access_token(identity=str(user.id))
            refresh = create_refresh_token(identity=str(user.id))

            return (
                jsonify(
                    {
                        "user": {
                            "refresh": refresh,
                            "access": access,
                            "email": user.email,
                            "username": user.username,
                        }
                    }
                ),
                HTTP_200_OK,
            )

    return jsonify({"error": "Wrong Credentials"}), HTTP_401_UNAUTHORIZED


# @auth.route("/me", methods=["GET"])
# @auth.get("/user")
@auth.get("/me")
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.filter_by(id=user_id).first()

    if user:
        return (
            jsonify(
                {
                    "username": user.username,
                    "email": user.email,
                }
            ),
            HTTP_200_OK,
        )

    return jsonify({"error": "User not found"}), HTTP_400_BAD_REQUEST


# @auth.post("/token/refresh")
@auth.get("/token/refresh")
@jwt_required(refresh=True)
def refresh_users_token():
    identity = get_jwt_identity()
    access = create_access_token(identity=identity)

    return jsonify({"access": access}), HTTP_200_OK


@auth.post("/logout")
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    revoked_tokens.add(jti)  # Add the token to the blacklist

    return jsonify({"message": "Successfully logged out"}), HTTP_200_OK


@auth.post("/logout_all")
@jwt_required()
def logout_all():
    user_id = get_jwt_identity()

    for token in revoked_tokens.copy():
        if token == user_id:
            revoked_tokens.remove(token)

    return jsonify({"message": "Logged out from all devices and sessions"}), HTTP_200_OK
