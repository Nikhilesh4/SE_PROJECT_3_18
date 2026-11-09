import { redirect } from "next/navigation";

// Search now lives on the Feed page; keep old links and bookmarks working.
export default function SearchRedirect() {
    redirect("/feed");
}
