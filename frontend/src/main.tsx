import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import { TenantProvider } from '@/context/TenantContext'
import { ThemeProvider } from '@/context/ThemeContext'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:  1000 * 60 * 5,   // 5 min — dados são "frescos" por 5min
      gcTime:     1000 * 60 * 30,  // 30 min em memória após desmontar (sem refetch ao voltar)
      retry: 1,
      refetchOnWindowFocus: false,  // não refetch ao trocar de aba do browser
      refetchOnReconnect: 'always',
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <TenantProvider>
              <App />
            </TenantProvider>
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
)
