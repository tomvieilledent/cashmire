import adapter from "@sveltejs/adapter-static";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    // SPA (ssr = false): every route falls back to index.html.
    adapter: adapter({ fallback: "index.html" }),
  },
};

export default config;
