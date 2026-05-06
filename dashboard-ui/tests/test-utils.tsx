/** 测试工具：为使用 TanStack Query 的组件提供 wrapper。 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render as rtlRender, type RenderOptions } from '@testing-library/react'
import type React from 'react'

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

export function renderWithQueryClient(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>,
) {
  const queryClient = createTestQueryClient()
  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
  }
  return {
    ...rtlRender(ui, { wrapper: Wrapper, ...options }),
    queryClient,
  }
}
