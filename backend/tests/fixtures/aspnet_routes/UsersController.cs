using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using MyApp.Models;
using MyApp.DTOs;
using MyApp.Services;

namespace MyApp.Controllers
{
    /// <summary>
    /// REST controller for user management endpoints.
    /// </summary>
    [ApiController]
    [Route("api/[controller]")]
    public class UsersController : ControllerBase
    {
        private readonly IUserService _userService;

        public UsersController(IUserService userService)
        {
            _userService = userService;
        }

        /// <summary>
        /// Get all users.
        /// </summary>
        [HttpGet]
        public async Task<ActionResult<IEnumerable<User>>> GetAll()
        {
            var users = await _userService.GetAllAsync();
            return Ok(users);
        }

        /// <summary>
        /// Get a user by ID.
        /// </summary>
        [HttpGet("{id}")]
        public async Task<ActionResult<User>> GetById(int id)
        {
            var user = await _userService.GetByIdAsync(id);
            if (user == null) return NotFound();
            return Ok(user);
        }

        /// <summary>
        /// Create a new user. Admin only.
        /// </summary>
        [HttpPost]
        [Authorize(Roles = "Admin")]
        public async Task<ActionResult<User>> Create([FromBody] CreateUserDto dto)
        {
            var user = await _userService.CreateAsync(dto);
            return CreatedAtAction(nameof(GetById), new { id = user.Id }, user);
        }

        /// <summary>
        /// Update an existing user. Admin only.
        /// </summary>
        [HttpPut("{id}")]
        [Authorize(Roles = "Admin")]
        public async Task<ActionResult> Update(int id, [FromBody] UpdateUserDto dto)
        {
            await _userService.UpdateAsync(id, dto);
            return NoContent();
        }

        /// <summary>
        /// Delete a user. Requires authentication.
        /// </summary>
        [HttpDelete("{id}")]
        [Authorize]
        public async Task<ActionResult> Delete(int id)
        {
            await _userService.DeleteAsync(id);
            return NoContent();
        }

        /// <summary>
        /// Search users by query string.
        /// </summary>
        [HttpGet("search")]
        public async Task<ActionResult<IEnumerable<User>>> Search(
            [FromQuery] string query,
            [FromQuery] int? page)
        {
            var users = await _userService.SearchAsync(query, page);
            return Ok(users);
        }

        /// <summary>
        /// Update user status. Admin or Moderator.
        /// </summary>
        [HttpPatch("{id}/status")]
        [Authorize(Roles = "Admin,Moderator")]
        public async Task<ActionResult<User>> UpdateStatus(
            int id,
            [FromBody] UpdateStatusDto dto)
        {
            var user = await _userService.UpdateStatusAsync(id, dto);
            return Ok(user);
        }

        /// <summary>
        /// Anonymous health check endpoint.
        /// </summary>
        [HttpGet("health")]
        [AllowAnonymous]
        public ActionResult<string> HealthCheck()
        {
            return Ok("healthy");
        }
    }
}
