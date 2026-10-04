import { useTranslation } from "react-i18next";
import classes from "./SkipLink.module.css";

export function SkipLink() {
  const { t } = useTranslation();
  return (
    <a className={classes.skip} href="#main">
      {t("common.skipToContent")}
    </a>
  );
}
