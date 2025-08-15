from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db,csrf
from .models import Post, User, Comment, Like, Tag
from app.forms import RegistrationForm, LoginForm, PostForm, CommentForm
from werkzeug.security import generate_password_hash, check_password_hash

@app.route('/')
def home():
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('home.html', posts=posts)

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if the email or username already exists
        existing_user = User.query.filter(
            (User.email == form.email.data) | (User.username == form.username.data)
        ).first()
        if existing_user:
            if existing_user.email == form.email.data:
                flash('Email is already registered. Please use a different email.', 'danger')
            elif existing_user.username == form.username.data:
                flash('Username is already taken. Please choose a different username.', 'danger')
            return render_template('register.html', form=form)

        # Hash the password before storing it
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        app.logger.info('New user registered: %s', user.email)
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Query the database for the user by email
        user = User.query.filter_by(email=form.email.data).first()

        # Check if the user exists and if the password is correct
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            app.logger.info('User %s logged in', user.id)
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Login unsuccessful. Please check your email and password.', 'danger')
    return render_template('login.html', form=form)

# Logout
@app.route('/logout')
@login_required
def logout():
    app.logger.info('User %s logged out', current_user.id)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# Create Post
@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        # Create a new Post
        post = Post(title=form.title.data, content=form.content.data, author=current_user)

        # Handle tags
        if form.tags.data:
            tag_names = [name.strip() for name in form.tags.data.split(',') if name.strip()]
            for name in tag_names:
                tag = Tag.query.filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name)
                post.tags.append(tag)

        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', form=form)

# Post detail
@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    # Like status for current user (for accessible aria-pressed)
    liked = False
    if current_user.is_authenticated:
        liked = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None
    like_count = post.likes.count()
    return render_template('post_detail.html', post=post, form=form, liked=liked, like_count=like_count)

# Users (admin-only)
@app.route('/users')
@login_required
def users():
    if not getattr(current_user, "is_admin", False):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))
    all_users = User.query.all()
    return render_template('users.html', users=all_users)

# Comment on a post
@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def comment(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(content=form.content.data, user_id=current_user.id, post_id=post.id)
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been added!', 'success')
        return redirect(url_for('post_detail', post_id=post.id))
    flash('Failed to add comment. Please try again.', 'danger')
    return redirect(url_for('post_detail', post_id=post.id))

# Traditional like (redirect)
@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()

    if like:
        db.session.delete(like)
        db.session.commit()
        app.logger.info('User %s unliked post %s', current_user.id, post.id)
        flash('You unliked the post.', 'info')
    else:
        like = Like(user_id=current_user.id, post_id=post.id)
        db.session.add(like)
        db.session.commit()
        app.logger.info('User %s liked post %s', current_user.id, post.id)
        flash('You liked the post!', 'success')

    return redirect(url_for('post_detail', post_id=post.id))

# --- LIKE: resilient toggle that won’t 500 on races ---
@app.post('/api/posts/<int:post_id>/like')
@login_required
def api_toggle_like(post_id):
    post = Post.query.get_or_404(post_id)

    # Toggle like atomically; handle duplicates gracefully
    try:
        existing = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
        if existing:
            db.session.delete(existing)
            action_liked = False
        else:
            db.session.add(Like(user_id=current_user.id, post_id=post_id))
            action_liked = True
        db.session.commit()
    except IntegrityError:
        # In case of race, just rollback and treat as "liked"
        db.session.rollback()
        action_liked = True

    like_count = Like.query.filter_by(post_id=post_id).count()
    is_liked = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first() is not None
    return jsonify(ok=True, liked=is_liked, like_count=like_count), 200
# User profile
@app.route('/user/<username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).all()
    return render_template('user_profile.html', user=user, posts=posts)

# Edit Post
@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)

    # Ensure only the owner can edit
    if post.author != current_user:
        abort(403)

    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data

        # Update tags
        post.tags.clear()
        if form.tags.data:
            tag_names = [name.strip() for name in form.tags.data.split(',') if name.strip()]
            for name in tag_names:
                tag = Tag.query.filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name)
                post.tags.append(tag)

        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('post_detail', post_id=post.id))

    # Pre-fill the form with current data
    form.title.data = post.title
    form.content.data = post.content
    form.tags.data = ', '.join([tag.name for tag in post.tags])
    return render_template('edit_post.html', form=form, post=post)

# Delete Post
@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    # Ensure only the owner can delete the post
    if post.author != current_user:
        abort(403)

    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'info')
    return redirect(url_for('home'))

# Browse by Tag
@app.route('/tag/<tag_name>')
def tag_posts(tag_name):
    tag = Tag.query.filter_by(name=tag_name).first_or_404()
    posts = tag.posts.order_by(Post.date_posted.desc()).all()
    return render_template('tag_posts.html', tag=tag, posts=posts)
# --- AJAX: add comment -------------------------------------------------------
@app.route('/api/posts/<int:post_id>/comments', methods=['POST'])
@login_required
def api_add_comment(post_id):
    post = Post.query.get_or_404(post_id)

    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify(ok=False, message="Comment can't be empty."), 400

    comment = Comment(content=content, user_id=current_user.id, post_id=post.id)
    db.session.add(comment)
    db.session.commit()

    comments_count = Comment.query.filter_by(post_id=post.id).count()

    payload = {
        "id": comment.id,
        "content": comment.content,
        "author_username": current_user.username,
        "author_initial": (current_user.username[:1] or 'U').upper(),
        "author_url": url_for('user_profile', username=current_user.username),
        "date_human": comment.date_posted.strftime('%Y-%m-%d %H:%M'),
    }
    return jsonify(ok=True, comments_count=comments_count, comment=payload), 200
