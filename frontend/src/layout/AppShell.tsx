import { AppShell as Shell, Burger, Button, Group, Stack, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useTranslation } from "react-i18next";
import { Outlet } from "react-router-dom";
import { useSession } from "@/auth/SessionProvider";
import { Bell } from "./Bell";
import { NavLinks } from "./NavLinks";
import { SkipLink } from "./SkipLink";

const WITH_BELL = new Set(["PERSONNEL", "HEAD_AUTHORITY"]);

// The signed-in frame: a navy header (app name, who is signed in, the bell, sign out), the
// role's navigation (a burger menu under 768 px) and the page in <main id="main">.
export function AppShell() {
  const { t } = useTranslation();
  const { user, signOut } = useSession();
  const [opened, { toggle, close }] = useDisclosure(false);
  if (!user) return null; // RequireRole only renders the shell for a signed-in user.

  return (
    <Shell
      header={{ height: 60 }}
      navbar={{ width: 240, breakpoint: "sm", collapsed: { mobile: !opened } }}
      padding="md"
    >
      <SkipLink />
      <Shell.Header bg="navy.6" c="white" px="md">
        <Group h="100%" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="sm"
              size="sm"
              color="white"
              aria-label={t(opened ? "nav.closeMenu" : "nav.openMenu")}
            />
            <Text fw={700}>{t("app.name")}</Text>
          </Group>
          <Group gap="sm" wrap="nowrap">
            <Stack gap={0} visibleFrom="xs" align="flex-end">
              <Text size="sm" fw={600}>
                {user.display_name}
              </Text>
              <Text size="xs">{t(`roles.${user.role}`)}</Text>
            </Stack>
            {WITH_BELL.has(user.role) && <Bell />}
            <Button variant="white" color="navy" size="xs" onClick={() => void signOut()}>
              {t("session.signOut")}
            </Button>
          </Group>
        </Group>
      </Shell.Header>
      <Shell.Navbar p="sm">
        <NavLinks user={user} onNavigate={close} />
      </Shell.Navbar>
      <Shell.Main id="main" tabIndex={-1}>
        <Outlet />
      </Shell.Main>
    </Shell>
  );
}
