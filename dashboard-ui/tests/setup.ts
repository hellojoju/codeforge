 
import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// jsdom doesn't support scrollIntoView
Element.prototype.scrollIntoView = vi.fn()
