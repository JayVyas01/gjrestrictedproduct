import { NavLink as MantineNavLink, Stack } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";
import type { Me } from "@/api/types";
import classes from "./NavLinks.module.css";
import { navItems } from "./navigation";

// The role's links. React Router marks the current one with aria-current="page".
export function NavLinks({ user, onNavigate }: { user: Me; onNavigate: () => void }) {
  const { t } = useTranslation();
  return (
    <Stack component="nav" aria-label={t("nav.label")} gap={4}>
      {navItems(user).map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={classes.link}
        >
          {({ isActive }) => (
            <MantineNavLink component="span" label={t(item.label)} active={isActive} />
          )}
        </NavLink>
      ))}
    </Stack>
  );
}
