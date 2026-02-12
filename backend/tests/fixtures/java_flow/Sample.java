package com.example.service;

import java.util.List;
import java.util.ArrayList;

/**
 * Sample service class for testing runtime flow parsing.
 */
public class SampleService {

    private final UserRepository userRepository;
    private final EmailService emailService;

    public SampleService(UserRepository userRepository, EmailService emailService) {
        this.userRepository = userRepository;
        this.emailService = emailService;
    }

    public static void main(String[] args) {
        System.out.println("Starting application");
        SampleService service = new SampleService(null, null);
        service.processUsers();
    }

    public List<User> processUsers() {
        List<User> users = userRepository.findAll();
        List<User> result = new ArrayList<>();

        for (User user : users) {
            if (user.isActive()) {
                validateUser(user);
                result.add(user);
            } else {
                logInactiveUser(user);
            }
        }

        return result;
    }

    private void validateUser(User user) {
        if (user.getEmail() == null) {
            throw new IllegalArgumentException("Email is required");
        }

        try {
            emailService.verifyEmail(user.getEmail());
        } catch (EmailException e) {
            handleEmailError(user, e);
        } finally {
            logValidation(user);
        }
    }

    private void handleEmailError(User user, EmailException e) {
        System.err.println("Email error for " + user.getUsername());
        notifyAdmin(user, e);
    }

    private void notifyAdmin(User user, Exception e) {
        emailService.sendAlert("admin@example.com", "Error for user: " + user.getId());
    }

    private void logInactiveUser(User user) {
        System.out.println("Inactive: " + user.getUsername());
    }

    private void logValidation(User user) {
        System.out.println("Validated: " + user.getUsername());
    }

    public int calculateScore(User user) {
        int score = 0;

        switch (user.getRole()) {
            case "ADMIN":
                score = 100;
                break;
            case "USER":
                score = 50;
                break;
            default:
                score = 10;
        }

        int bonus = 0;
        int i = 0;
        while (i < user.getPostCount()) {
            bonus += computeBonus(i);
            i++;
        }

        do {
            score = adjustScore(score);
        } while (score < 0);

        return score + bonus;
    }

    private int computeBonus(int index) {
        return index * 2;
    }

    private int adjustScore(int score) {
        return score + 10;
    }

    @GetMapping("/report")
    public Report generateReport() {
        List<User> users = processUsers();
        return buildReport(users);
    }

    @PostMapping("/import")
    public void importData(@RequestBody ImportRequest request) {
        processImport(request);
    }

    @Scheduled(fixedRate = 60000)
    public void scheduledCleanup() {
        cleanupInactiveUsers();
    }

    private Report buildReport(List<User> users) {
        return new Report(users);
    }

    private void processImport(ImportRequest request) {
        for (User user : request.getUsers()) {
            validateUser(user);
        }
    }

    private void cleanupInactiveUsers() {
        List<User> inactive = userRepository.findInactive();
        for (User user : inactive) {
            userRepository.delete(user);
        }
    }

    public abstract void abstractMethod();

    public static int staticHelper(int value) {
        return value * 2;
    }
}
