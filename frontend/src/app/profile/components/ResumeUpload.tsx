"use client";

import { ChangeEvent } from "react";
import { AxiosError } from "axios";
import api from "@/lib/api";
import { ProfileData } from "./types";

type ErrorResponse = {
    detail?: string;
};

type ResumeUploadProps = {
    isUploading: boolean;
    onUploadStart: () => void;
    onUploadEnd: () => void;
    onUploadSuccess: (profile: ProfileData) => void;
    onError: (message: string) => void;
};

const MAX_FILE_BYTES = 5 * 1024 * 1024;

export default function ResumeUpload({
    isUploading,
    onUploadStart,
    onUploadEnd,
    onUploadSuccess,
    onError,
}: ResumeUploadProps) {
    const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) {
            return;
        }

        if (file.type !== "application/pdf") {
            onError("Only PDF files are accepted.");
            event.target.value = "";
            return;
        }

        if (file.size > MAX_FILE_BYTES) {
            onError("File size must be under 5MB.");
            event.target.value = "";
            return;
        }

        const form = new FormData();
        form.append("file", file);

        onUploadStart();
        onError("");

        try {
            const { data } = await api.post<ProfileData>("/profile/upload-resume", form, {
                headers: {
                    "Content-Type": "multipart/form-data",
                },
            });
            onUploadSuccess(data);
        } catch (error) {
            const axiosErr = error as AxiosError<ErrorResponse>;
            const detail =
                axiosErr.response?.data?.detail ||
                "Upload failed. Please try again in a moment.";
            onError(detail);
        } finally {
            onUploadEnd();
            event.target.value = "";
        }
    };

    return (
        <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-6">
            <h2 className="text-xl font-semibold text-white">Upload Resume</h2>
            <p className="mt-2 text-sm text-slate-300">
                Upload a PDF resume to automatically extract your profile using AI.
            </p>

            <label className="mt-5 block">
                <input
                    type="file"
                    accept="application/pdf"
                    onChange={handleFileChange}
                    disabled={isUploading}
                    className="block w-full cursor-pointer rounded-lg border border-slate-600 bg-slate-950 px-4 py-3 text-sm text-slate-200 file:mr-4 file:rounded-md file:border-0 file:bg-cyan-500 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-950 hover:file:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
                />
            </label>

            {isUploading && (
                <p className="mt-4 text-sm text-cyan-300">
                    Extracting your profile using Groq AI with Gemini fallback. This may take up to 10-15 seconds.
                </p>
            )}
        </div>
    );
}
