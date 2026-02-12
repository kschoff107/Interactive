package models

import (
	"time"

	"gorm.io/gorm"
)

type User struct {
	gorm.Model
	Name       string     `gorm:"column:name;type:varchar(100);not null" json:"name"`
	Email      string     `gorm:"column:email;uniqueIndex;not null" json:"email"`
	Password   string     `gorm:"column:password;type:varchar(255);not null" json:"-"`
	Age        int        `gorm:"default:0" json:"age"`
	IsActive   bool       `gorm:"default:true" json:"is_active"`
	DeptID     uint       `gorm:"column:department_id" json:"department_id"`
	Department Department `gorm:"foreignKey:DeptID" json:"department"`
	Posts      []Post     `gorm:"foreignKey:UserID" json:"posts"`
	Profile    *Profile   `gorm:"foreignKey:UserID" json:"profile"`
}

type Post struct {
	gorm.Model
	Title     string `gorm:"column:title;type:varchar(200);not null" json:"title"`
	Body      string `gorm:"column:body;type:text" json:"body"`
	Published bool   `gorm:"default:false" json:"published"`
	UserID    uint   `gorm:"column:user_id;not null" json:"user_id"`
	User      User   `gorm:"foreignKey:UserID" json:"user"`
	Comments  []Comment `gorm:"foreignKey:PostID" json:"comments"`
}

type Department struct {
	gorm.Model
	Name  string `gorm:"column:name;type:varchar(100);not null" json:"name"`
	Code  string `gorm:"column:code;type:varchar(20);uniqueIndex;not null" json:"code"`
	Users []User `gorm:"foreignKey:DeptID" json:"users"`
}

type Comment struct {
	gorm.Model
	Content string `gorm:"column:content;type:text;not null" json:"content"`
	PostID  uint   `gorm:"column:post_id;not null" json:"post_id"`
	UserID  uint   `gorm:"column:user_id;not null" json:"user_id"`
	Post    Post   `gorm:"foreignKey:PostID" json:"post"`
	User    User   `gorm:"foreignKey:UserID" json:"user"`
}

type Profile struct {
	gorm.Model
	Bio       string    `gorm:"column:bio;type:text" json:"bio"`
	AvatarURL string    `gorm:"column:avatar_url;type:varchar(500)" json:"avatar_url"`
	UserID    uint      `gorm:"column:user_id;uniqueIndex;not null" json:"user_id"`
	BirthDate *time.Time `gorm:"column:birth_date" json:"birth_date"`
}
