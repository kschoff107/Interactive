const express = require('express');
const app = express();

// Middleware
const authenticate = require('./middleware/auth');
const isAdmin = require('./middleware/admin');

// Direct app routes
app.get('/health', (req, res) => res.json({ ok: true }));
app.get('/version', (req, res) => res.json({ version: '1.0.0' }));

// Router for /api/v1/users
const userRouter = express.Router();

userRouter.get('/', getAllUsers);
userRouter.get('/:id', getUserById);
userRouter.post('/', authenticate, createUser);
userRouter.put('/:id', authenticate, updateUser);
userRouter.delete('/:id', authenticate, isAdmin, deleteUser);

// Router for /api/v1/posts
const postRouter = express.Router();

postRouter.get('/', getAllPosts);
postRouter.get('/:id', getPostById);
postRouter.post('/', authenticate, createPost);
postRouter.patch('/:id', authenticate, updatePost);

// Mount routers with prefix
app.use('/api/v1/users', userRouter);
app.use('/api/v1/posts', postRouter);

// Error handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Internal server error' });
});

module.exports = app;
