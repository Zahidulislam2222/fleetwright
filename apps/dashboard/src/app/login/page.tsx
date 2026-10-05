import type { Metadata } from "next";
import { LoginFlow } from "@/components/console/LoginFlow";
import copy from "@/content/prototype.json";

export const metadata: Metadata = { title: { absolute: copy.auth.title }, robots: { index: false, follow: false } };

export default function LoginPage() {
  return <LoginFlow />;
}
