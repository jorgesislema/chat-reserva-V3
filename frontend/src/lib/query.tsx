'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'

export interface QueryProviderProps {
  client: QueryClient
  children: ReactNode
}

export function QueryProvider({ client, children }: QueryProviderProps) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}