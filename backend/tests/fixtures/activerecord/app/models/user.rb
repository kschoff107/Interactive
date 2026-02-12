class User < ApplicationRecord
  has_many :posts, dependent: :destroy
  has_many :comments, dependent: :destroy
  belongs_to :department
  has_one :profile
  has_and_belongs_to_many :roles

  validates :name, presence: true
  validates :email, presence: true, uniqueness: true
end
