from . import db
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import UniqueConstraint

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    profile_pic = db.Column(db.String(120), default='default.jpg')
    # Optional admin flag (used in /users route)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # Relationship to Post (backref creates 'author' in Post)
    posts = db.relationship('Post', backref='author', lazy=True)

post_tags = db.Table(
    'post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Cascade deletes related comments and likes
    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete")
    # Dynamic so we can query counts efficiently
    likes = db.relationship('Like', backref='post', lazy='dynamic', cascade="all, delete")
    # Many-to-many Post <-> Tag
    tags = db.relationship('Tag', secondary=post_tags, backref=db.backref('posts', lazy='dynamic'))

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    # Relationship to User
    author = db.relationship('User', backref='comments', lazy=True)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'post_id', name='uq_user_post_like'),
    )

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
