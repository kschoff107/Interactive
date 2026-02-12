package com.example.controllers;

import com.example.models.User;
import com.example.dto.UserDto;
import com.example.service.UserService;
import org.springframework.web.bind.annotation.*;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.http.ResponseEntity;
import javax.annotation.security.RolesAllowed;
import java.util.List;

/**
 * REST controller for user management endpoints.
 */
@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    public List<User> getAllUsers() {
        return userService.findAll();
    }

    @GetMapping("/{id}")
    public ResponseEntity<User> getUserById(@PathVariable Long id) {
        return ResponseEntity.ok(userService.findById(id));
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public User createUser(@RequestBody UserDto dto) {
        return userService.create(dto);
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public User updateUser(@PathVariable Long id, @RequestBody UserDto dto) {
        return userService.update(id, dto);
    }

    @DeleteMapping("/{id}")
    @RolesAllowed({"ADMIN"})
    public void deleteUser(@PathVariable Long id) {
        userService.delete(id);
    }

    @GetMapping("/search")
    public List<User> searchUsers(@RequestParam String query, @RequestParam(required = false) Integer page) {
        return userService.search(query, page);
    }

    @PatchMapping("/{id}/status")
    @PreAuthorize("hasAnyRole('ADMIN', 'MODERATOR')")
    public User updateStatus(@PathVariable Long id, @RequestBody Map<String, Object> updates) {
        return userService.updateStatus(id, updates);
    }

    @RequestMapping(value = "/legacy", method = RequestMethod.GET)
    public List<User> legacyEndpoint() {
        return userService.findAll();
    }
}
