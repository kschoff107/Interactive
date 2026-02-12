"""
Django models fixture for testing the DjangoParser.

Defines a small blog-like application with Users, Posts, Tags,
and Comments to exercise foreign keys, many-to-many relationships,
custom table names, Meta options, and various field types.
"""

from django.db import models


class User(models.Model):
    """User account for the blog platform."""
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(max_length=254, unique=True)
    bio = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'blog_users'
        indexes = [
            models.Index(fields=['username'], name='idx_user_username'),
            models.Index(fields=['email'], name='idx_user_email'),
        ]

    def __str__(self):
        return self.username


class Tag(models.Model):
    """Content tag for categorizing posts."""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True)

    def __str__(self):
        return self.name


class Post(models.Model):
    """Blog post authored by a user, optionally tagged."""
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag, blank=True)
    published = models.BooleanField(default=False)
    view_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'blog_posts'
        unique_together = [('author', 'slug')]

    def __str__(self):
        return self.title


class Comment(models.Model):
    """Comment on a blog post, supporting nested replies."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    body = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['post', 'created_at'], name='idx_comment_post_date'),
        ]
