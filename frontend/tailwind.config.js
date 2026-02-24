/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      gridTemplateColumns: {
        emulator: "320px 1fr 360px",
      },
    },
  },
  plugins: [],
};
