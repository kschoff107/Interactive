using Microsoft.EntityFrameworkCore;
using MyApp.Models;

namespace MyApp.Data
{
    /// <summary>
    /// Application database context with DbSet declarations and Fluent API config.
    /// </summary>
    public class AppDbContext : DbContext
    {
        public DbSet<User> Users { get; set; }
        public DbSet<Post> Posts { get; set; }
        public DbSet<Comment> Comments { get; set; }

        public AppDbContext(DbContextOptions<AppDbContext> options)
            : base(options)
        {
        }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            // Configure User entity via Fluent API
            modelBuilder.Entity<User>().ToTable("Users");
            modelBuilder.Entity<User>().HasKey(u => u.Id);
            modelBuilder.Entity<User>().Property(u => u.Username).HasMaxLength(100).IsRequired();
            modelBuilder.Entity<User>().Property(u => u.Email).HasMaxLength(255).IsRequired();
            modelBuilder.Entity<User>().HasMany(u => u.Posts).WithOne(p => p.Author);

            // Configure Post entity
            modelBuilder.Entity<Post>().ToTable("Posts");
            modelBuilder.Entity<Post>().HasKey(p => p.Id);
            modelBuilder.Entity<Post>().Property(p => p.Title).HasMaxLength(200).IsRequired();
            modelBuilder.Entity<Post>().HasMany(p => p.Comments).WithOne(c => c.Post);

            // Configure Comment entity with custom table name
            modelBuilder.Entity<Comment>().ToTable("blog_comments");
            modelBuilder.Entity<Comment>().Property(c => c.Body).HasMaxLength(2000).IsRequired();
            modelBuilder.Entity<Comment>().HasOne(c => c.Author).WithMany();

            base.OnModelCreating(modelBuilder);
        }
    }
}
