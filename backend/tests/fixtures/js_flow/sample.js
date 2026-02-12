const express = require('express');
const { validateInput } = require('./utils');

// Regular function declaration
function processData(items) {
  const results = [];
  for (let i = 0; i < items.length; i++) {
    if (items[i].active) {
      const transformed = transformItem(items[i]);
      results.push(transformed);
    } else {
      logSkipped(items[i]);
    }
  }
  return results;
}

// Async function
async function fetchUsers(query) {
  try {
    const response = await httpClient.get('/api/users', { params: query });
    const users = parseResponse(response);
    return users;
  } catch (error) {
    handleError(error);
    return [];
  }
}

// Arrow function
const transformItem = (item) => {
  const name = formatName(item.name);
  const score = calculateScore(item.metrics);
  return { name, score, id: item.id };
};

// Class with methods
class UserService {
  constructor(db) {
    this.db = db;
  }

  async findById(id) {
    const user = await this.db.query('SELECT * FROM users WHERE id = ?', [id]);
    if (!user) {
      throw new NotFoundError('User not found');
    }
    return formatUser(user);
  }

  async createUser(data) {
    validateInput(data);
    const hashed = await hashPassword(data.password);
    const user = await this.db.insert('users', { ...data, password: hashed });
    sendWelcomeEmail(user.email);
    return user;
  }

  deleteUser(id) {
    const existing = this.findById(id);
    if (existing) {
      this.db.delete('users', id);
      clearCache(id);
    }
  }
}

// Entry point
function main() {
  const app = express();
  const service = new UserService(getDatabase());
  setupRoutes(app, service);
  app.listen(3000);
}

module.exports = main;
