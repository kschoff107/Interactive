<?php

use App\Http\Controllers\AuthController;
use App\Http\Controllers\UserController;
use App\Http\Controllers\PostController;
use App\Http\Controllers\CommentController;
use App\Http\Controllers\SearchController;
use Illuminate\Support\Facades\Route;

Route::post('/auth/login', [AuthController::class, 'login']);
Route::post('/auth/register', [AuthController::class, 'register']);

Route::middleware('auth:sanctum')->group(function () {
    Route::get('/users', [UserController::class, 'index']);
    Route::post('/users', [UserController::class, 'store']);
    Route::get('/users/{user}', [UserController::class, 'show']);
    Route::put('/users/{user}', [UserController::class, 'update']);
    Route::delete('/users/{user}', [UserController::class, 'destroy']);

    Route::get('/me', [UserController::class, 'me']);
    Route::post('/auth/logout', [AuthController::class, 'logout']);
});

Route::prefix('api/v1')->group(function () {
    Route::resource('posts', PostController::class);
    Route::apiResource('comments', CommentController::class);
});

Route::get('/search', [SearchController::class, 'index']);
Route::get('/health', 'HealthController@check');
