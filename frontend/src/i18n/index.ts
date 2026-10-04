import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";

// English only for now, with no language detection. React already escapes text,
// so i18next must not escape it a second time.
export const defaultNS = "translation";
export const resources = { en: { translation: en } } as const;

void i18n.use(initReactI18next).init({
  resources,
  lng: "en",
  fallbackLng: "en",
  defaultNS,
  interpolation: { escapeValue: false },
  initAsync: false,
  returnNull: false,
});

export default i18n;
