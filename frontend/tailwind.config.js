/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      gridTemplateColumns: {
        emulator: "220px 1fr 1fr 240px",
      },
    },
  },
  plugins: [],
};
