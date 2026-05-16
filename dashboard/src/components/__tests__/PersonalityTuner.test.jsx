import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import PersonalityTuner from '../PersonalityTuner'

const mockSettings = {
    provider: 'openai',
    model: 'gpt-4o',
    temperature: 0.7,
    empathy: 80,
    humor: 50,
    formality: 20,
    system_prompt: 'Test prompt'
}

describe('PersonalityTuner Component', () => {
    it('renders with initial settings', () => {
        render(<PersonalityTuner settings={mockSettings} onChange={() => {}} />)
        
        // Check if provider is selected
        const openaiBtn = screen.getByText('OpenAI').closest('button')
        expect(openaiBtn).toHaveClass('bg-primary')
        
        // Check if model name is in input
        const modelInput = screen.getByDisplayValue('gpt-4o')
        expect(modelInput).toBeInTheDocument()
        
        // Check if system prompt is in textarea
        const promptArea = screen.getByDisplayValue('Test prompt')
        expect(promptArea).toBeInTheDocument()
    })

    it('calls onChange when provider is changed', () => {
        const handleChange = vi.fn()
        render(<PersonalityTuner settings={mockSettings} onChange={handleChange} />)
        
        const anthropicBtn = screen.getByText('Anthropic').closest('button')
        fireEvent.click(anthropicBtn)
        
        expect(handleChange).toHaveBeenCalledWith({ provider: 'anthropic' })
    })

    it('calls onChange when model name is typed', () => {
        const handleChange = vi.fn()
        render(<PersonalityTuner settings={mockSettings} onChange={handleChange} />)
        
        const modelInput = screen.getByDisplayValue('gpt-4o')
        fireEvent.change(modelInput, { target: { value: 'claude-3-sonnet' } })
        
        expect(handleChange).toHaveBeenCalledWith({ model: 'claude-3-sonnet' })
    })

    it('renders skeleton when settings are missing', () => {
        render(<PersonalityTuner settings={null} onChange={() => {}} />)
        // Skeleton has animate-pulse class
        const skeleton = screen.getByRole('generic', { hidden: true }).querySelector('.animate-pulse')
        expect(skeleton).toBeInTheDocument()
    })
})
