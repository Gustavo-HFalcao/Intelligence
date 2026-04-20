import type { Config } from 'tailwindcss'
import tailwindAnimate from 'tailwindcss-animate'

const config: Config = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      // ── Design tokens portados de bomtempo/core/styles.py + components/theme.py ──
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },

        // Deep Tectonic legacy aliases
        'bg-void':    'var(--void)',
        'bg-depth':   'var(--depth)',
        'bg-surface': 'var(--surface)',
        'bg-elevated':'var(--elevated)',
        copper: {
          DEFAULT: '#C98B2A',
          light:   '#E0A63B',
          soft:    '#F5D78E',
        },
        patina: {
          DEFAULT: '#2A9D8F',
          dark:    '#1d7066',
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        card:    '6px',
        control: '3px',
      },
      fontFamily: {
        display: ["'Rajdhani'", 'sans-serif'],
        body:    ["'Outfit'", 'sans-serif'],
        mono:    ["'JetBrains Mono'", 'monospace'],
        sans:    ["'Outfit'", 'sans-serif'],
      },
      boxShadow: {
        card:       '0 4px 30px rgba(0, 0, 0, 0.3)',
        'card-hover':'0 16px 48px rgba(0, 0, 0, 0.5), 0 0 1px rgba(201, 139, 42, 0.3)',
        'glow-copper':'0 0 20px rgba(201, 139, 42, 0.15)',
        'glow-patina':'0 0 20px rgba(42, 157, 143, 0.15)',
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 0.5s ease-out",
      },
      backdropBlur: {
        glass: '12px',
      },
    },
  },
  plugins: [tailwindAnimate],
}

export default config
