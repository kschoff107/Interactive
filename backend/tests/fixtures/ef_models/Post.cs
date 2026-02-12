using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace MyApp.Models
{
    /// <summary>
    /// Post entity representing a blog post authored by a user.
    /// </summary>
    [Table("Posts")]
    public class Post
    {
        [Key]
        public int Id { get; set; }

        [Required]
        [StringLength(200)]
        public string Title { get; set; }

        public string Content { get; set; }

        [Required]
        public bool IsPublished { get; set; }

        public int ViewCount { get; set; }

        public DateTime CreatedAt { get; set; }

        public DateTime? UpdatedAt { get; set; }

        [ForeignKey("Author")]
        public int AuthorId { get; set; }

        // Navigation — many-to-one back to User
        public User Author { get; set; }

        // Navigation — one-to-many to comments
        public ICollection<Comment> Comments { get; set; }

        [Column("category_id")]
        public int? CategoryId { get; set; }
    }
}
