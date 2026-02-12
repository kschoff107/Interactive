using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace MyApp.Models
{
    /// <summary>
    /// User entity for authentication and profile management.
    /// </summary>
    [Table("Users")]
    public class User
    {
        [Key]
        [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
        public int Id { get; set; }

        [Required]
        [StringLength(100)]
        [Column("user_name")]
        public string Username { get; set; }

        [Required]
        [StringLength(255)]
        public string Email { get; set; }

        [Required]
        public string PasswordHash { get; set; }

        public int? Age { get; set; }

        [Required]
        public bool IsActive { get; set; }

        public DateTime CreatedAt { get; set; }

        [ForeignKey("Department")]
        public int DepartmentId { get; set; }

        // Navigation property — many-to-one
        public Department Department { get; set; }

        // Navigation property — one-to-many
        public ICollection<Post> Posts { get; set; }

        [NotMapped]
        public string DisplayName { get; set; }
    }
}
