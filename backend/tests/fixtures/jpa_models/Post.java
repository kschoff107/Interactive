package com.example.models;

import javax.persistence.*;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Post entity representing a blog post authored by a user.
 */
@Entity
@Table(name = "posts")
public class Post {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private Long id;

    @Column(name = "title", nullable = false, length = 200)
    private String title;

    @Column(name = "content", columnDefinition = "TEXT")
    private String content;

    @Column(name = "published")
    private Boolean published;

    @Column(name = "view_count")
    private Integer viewCount;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "author_id", nullable = false)
    private User author;

    @OneToMany(mappedBy = "post", cascade = CascadeType.ALL)
    private List<Comment> comments;

    @OneToOne(cascade = CascadeType.ALL)
    @JoinColumn(name = "metadata_id", referencedColumnName = "id")
    private PostMetadata metadata;

    public Post() {}

    public Long getId() { return id; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
}
