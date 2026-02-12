const { Model, DataTypes } = require('sequelize');
const sequelize = require('../config/database');

// Pattern 1: sequelize.define()
const User = sequelize.define('User', {
  id: {
    type: DataTypes.INTEGER,
    primaryKey: true,
    autoIncrement: true,
  },
  username: {
    type: DataTypes.STRING,
    allowNull: false,
    unique: true,
  },
  email: DataTypes.STRING,
  age: {
    type: DataTypes.INTEGER,
    defaultValue: 0,
  },
  role: {
    type: DataTypes.ENUM,
    values: ['user', 'admin'],
    defaultValue: 'user',
  },
}, {
  tableName: 'users',
  timestamps: true,
});

// Pattern 2: class-based Model.init()
class Post extends Model {}
Post.init({
  title: {
    type: DataTypes.STRING,
    allowNull: false,
  },
  content: {
    type: DataTypes.TEXT,
    allowNull: true,
  },
  published: {
    type: DataTypes.BOOLEAN,
    defaultValue: false,
  },
  authorId: {
    type: DataTypes.INTEGER,
    references: {
      model: 'users',
      key: 'id',
    },
  },
}, {
  sequelize,
  tableName: 'posts',
});

// Associations
User.hasMany(Post, { foreignKey: 'authorId' });
Post.belongsTo(User, { foreignKey: 'authorId' });

module.exports = { User, Post };
