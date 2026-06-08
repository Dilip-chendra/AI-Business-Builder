import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import business from '../../data/business.json';
import Page from '../page';

jest.mock('../components/Hero', () => ({
  Hero: ({ business }: any) => <div data-testid="hero">{business.headline}</div>,
}));

describe('Page Component', () => {
  it('renders the Hero component with the correct headline', () => {
    render(<Page />);
    expect(screen.getByTestId('hero')).toHaveTextContent(business.headline);
  });

  it('displays the offer lines correctly', () => {
    render(<Page />);
    const offerLines = ["An AI code editor that writes into the real workspace.", "A local validation business for testing the AI Code Editor."];
    offerLines.forEach(line => {
      expect(screen.getByText(line)).toBeInTheDocument();
    });
  });

  it('displays the benefit lines correctly', () => {
    render(<Page />);
    const benefitLines = ["Built for developers", "Tone of voice: technical and clear", "subscription"];
    benefitLines.forEach(item => {
      expect(screen.getByText(item)).toBeInTheDocument();
    });
  });
});