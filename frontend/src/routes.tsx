import { Container, Title } from "@mantine/core";
import type { RouteObject } from "react-router-dom";
import { useTranslation } from "react-i18next";

function HomePlaceholder() {
  const { t } = useTranslation();
  return (
    <Container component="main" id="main" py="xl">
      <Title order={1}>{t("app.name")}</Title>
    </Container>
  );
}

// The app's routes. Later tasks add sign-in, the shell and each role's screens.
export const routes: RouteObject[] = [{ path: "*", element: <HomePlaceholder /> }];
