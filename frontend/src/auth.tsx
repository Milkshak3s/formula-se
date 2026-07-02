import { createContext, useContext, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api/client";
import { ROLE_LEVEL, type Role, type User } from "./api/types";

interface AuthValue {
  user: User | null;
  isLoading: boolean;
  hasRole: (role: Role) => boolean;
  refresh: () => void;
}

const AuthContext = createContext<AuthValue>({
  user: null,
  isLoading: true,
  hasRole: () => false,
  refresh: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api.me();
      } catch {
        return null;
      }
    },
    retry: false,
    staleTime: 60_000,
  });

  const user = data ?? null;
  const value: AuthValue = {
    user,
    isLoading,
    hasRole: (role) => !!user && ROLE_LEVEL[user.role] >= ROLE_LEVEL[role],
    refresh: () => qc.invalidateQueries({ queryKey: ["me"] }),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
