"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { UserPrincipal } from "./types";

export const DEMO_USERS: UserPrincipal[] = [
  {
    username: "sofia",
    name: "Sofia Schmidt",
    roles: ["admin", "legal"],
    plant: null,
    email: "sofia.schmidt@halden.pl",
  },
  {
    username: "elena",
    name: "Elena Rostova",
    roles: ["procurement"],
    plant: "DE-HAM",
    email: "elena.rostova@halden.de",
  },
  {
    username: "mehmet",
    name: "Mehmet Yilmaz",
    roles: ["quality"],
    plant: "DE-HAM",
    email: "mehmet.yilmaz@halden.de",
  },
  {
    username: "lukas",
    name: "Lukas Bauer",
    roles: ["support"],
    plant: "DE-STR",
    email: "lukas.bauer@halden.de",
  },
  {
    username: "viewer",
    name: "Guest Viewer",
    roles: ["viewer"],
    plant: "DE-HAM",
    email: "guest.viewer@halden.de",
  },
  {
    username: "jana",
    name: "Jana Weber",
    roles: ["admin", "analyst"],
    plant: null,
    email: "jana.weber@halden.de",
  },
];

interface AuthContextType {
  currentUser: UserPrincipal;
  setUser: (user: UserPrincipal) => void;
  getAuthHeaders: () => Record<string, string>;
}

const AuthContext = createContext<AuthContextType>({
  currentUser: DEMO_USERS[0],
  setUser: () => {},
  getAuthHeaders: () => ({}),
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUser] = useState<UserPrincipal>(DEMO_USERS[0]);

  useEffect(() => {
    const saved = localStorage.getItem("fieldkit_user");
    if (saved) {
      try {
        const found = DEMO_USERS.find((u) => u.username === saved);
        if (found) setCurrentUser(found);
      } catch {
        // Fallback to default
      }
    }
  }, []);

  const handleSetUser = (user: UserPrincipal) => {
    setCurrentUser(user);
    localStorage.setItem("fieldkit_user", user.username);
  };

  const getAuthHeaders = (): Record<string, string> => {
    // Generate standard unverified JWT token with claims
    const claims = {
      sub: currentUser.username,
      preferred_username: currentUser.username,
      email: currentUser.email,
      realm_access: { roles: currentUser.roles },
      plant: currentUser.plant,
    };
    const b64Header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
    const b64Payload = btoa(JSON.stringify(claims));
    const token = `${b64Header}.${b64Payload}.`;
    return {
      Authorization: `Bearer ${token}`,
      "X-User-Plant": currentUser.plant || "",
      "X-User-Role": currentUser.roles[0] || "viewer",
    };
  };

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        setUser: handleSetUser,
        getAuthHeaders,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
