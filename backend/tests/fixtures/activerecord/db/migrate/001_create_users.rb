class CreateUsers < ActiveRecord::Migration[7.0]
  def change
    create_table :users do |t|
      t.string :name, null: false
      t.string :email, null: false, index: { unique: true }
      t.string :password_digest, null: false
      t.references :department, foreign_key: true
      t.integer :age, default: 0
      t.boolean :active, default: true
      t.timestamps
    end

    add_index :users, :email, unique: true

    create_table :posts do |t|
      t.string :title, null: false
      t.text :body
      t.references :user, foreign_key: true
      t.boolean :published, default: false
      t.timestamps
    end

    create_table :departments do |t|
      t.string :name, null: false
      t.string :code, null: false
      t.timestamps
    end

    create_table :comments do |t|
      t.text :content, null: false
      t.references :post, foreign_key: true
      t.references :user, foreign_key: true
      t.timestamps
    end
  end
end
