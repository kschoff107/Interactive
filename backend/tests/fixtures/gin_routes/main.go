package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.Default()

	// Health check
	r.GET("/health", healthCheck)
	r.GET("/version", getVersion)

	// API v1 group
	api := r.Group("/api/v1")
	api.Use(AuthMiddleware())
	{
		// Users group
		users := api.Group("/users")
		users.GET("", getAllUsers)
		users.POST("", createUser)
		users.GET("/:id", getUserByID)
		users.PUT("/:id", updateUser)
		users.DELETE("/:id", deleteUser)

		// Posts group
		posts := api.Group("/posts")
		posts.GET("", getAllPosts)
		posts.POST("", createPost)
		posts.GET("/:id", getPostByID)
		posts.PUT("/:id", updatePost)
		posts.DELETE("/:id", deletePost)
	}

	// Public routes
	public := r.Group("/public")
	{
		public.GET("/search", searchHandler)
		public.GET("/categories", listCategories)
	}

	// Admin routes
	admin := r.Group("/admin")
	admin.Use(AdminAuthMiddleware())
	{
		admin.GET("/dashboard", adminDashboard)
		admin.GET("/users", adminListUsers)
		admin.DELETE("/users/:id", adminDeleteUser)
	}

	r.Run(":8080")
}

func healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

func getVersion(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"version": "1.0.0"})
}
