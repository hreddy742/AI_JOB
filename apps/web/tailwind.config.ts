import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        bg: "var(--color-bg)",
        fg: "var(--color-text-primary)",
        muted: "var(--color-text-secondary)",
        card: "var(--color-surface-2)",
        border: "var(--color-border-sub)",
        ring: "var(--color-border-focus)",
        primary: {
          DEFAULT: "var(--color-accent)",
          foreground: "#ffffff"
        },
        success: "var(--color-success)",
        warning: "var(--color-warning)",
        danger: "var(--color-error)"
      },
      fontFamily: {
        sans: ["var(--font-dm-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-fraunces)", "Georgia", "serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"]
      },
      borderRadius: {
        lg: "var(--radius-lg)",
        md: "var(--radius-md)",
        sm: "var(--radius-sm)"
      },
      boxShadow: {
        glass: "var(--shadow-glass)",
        card: "var(--shadow-md)"
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-6px)" }
        },
        pulseWave: {
          "0%": { opacity: "0.3", transform: "scale(0.9)" },
          "100%": { opacity: "0", transform: "scale(1.8)" }
        }
      },
      animation: {
        float: "float 3s ease-in-out infinite",
        pulseWave: "pulseWave 1.8s cubic-bezier(0.22,1,0.36,1) infinite"
      }
    }
  },
  plugins: []
};

export default config;
