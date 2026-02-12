const mongoose = require('mongoose');
const { Schema } = mongoose;

const userSchema = new Schema({
  name: { type: String, required: true },
  email: { type: String, required: true, unique: true },
  password: { type: String, required: true },
  age: { type: Number, default: 0 },
  role: { type: String, enum: ['user', 'admin', 'moderator'], default: 'user' },
  department: { type: Schema.Types.ObjectId, ref: 'Department' },
  posts: [{ type: Schema.Types.ObjectId, ref: 'Post' }],
  tags: [String],
  isActive: Boolean,
  createdAt: { type: Date, default: Date.now },
});

const User = mongoose.model('User', userSchema);

const postSchema = new Schema({
  title: { type: String, required: true },
  content: { type: String },
  author: { type: Schema.Types.ObjectId, ref: 'User' },
  likes: { type: Number, default: 0 },
  published: { type: Boolean, default: false },
});

const Post = mongoose.model('Post', postSchema);

module.exports = { User, Post };
