/** Shared by the client store and the server-rendered pre-paint theme script. */
export const PROTOTYPE_STORAGE_KEY = "fleetwright.prototype";

/** Runs before paint: pins the saved console theme so a hard reload never flashes the other theme. */
export const themeBootScript = `(function(){try{var s=JSON.parse(sessionStorage.getItem(${JSON.stringify(PROTOTYPE_STORAGE_KEY)})||"{}");if(s.theme==="light"||s.theme==="dark")document.documentElement.dataset.consoleTheme=s.theme}catch(e){}})()`;
