// Spec calls for `sources/[name].tsx`. React Router v6 uses path params
// instead of file-based routing, so the implementation lives in
// ./detail.tsx; this file is a stable re-export so the layout matches
// the gooey-plan file map verbatim.
export { default } from "./detail";
