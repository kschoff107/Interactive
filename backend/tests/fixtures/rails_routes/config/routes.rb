Rails.application.routes.draw do
  namespace :api do
    namespace :v1 do
      resources :users do
        resources :posts, only: [:index, :create]
      end

      resources :departments, only: [:index, :show, :create, :update]

      resource :profile, only: [:show, :update]

      get '/search', to: 'search#index'
      post '/auth/login', to: 'auth#login'
      delete '/auth/logout', to: 'auth#logout'
    end
  end

  resources :comments, except: [:new, :edit]

  root 'home#index'
end
