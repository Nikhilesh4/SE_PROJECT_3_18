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
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-slate-900 tracking-tight">Upload Resume</h2>
            <p className="mt-1 text-sm text-slate-600">
                Upload a PDF resume to automatically extract your profile using AI.
            </p>

            <label className="mt-5 block">
                <input
                    type="file"
                    accept="application/pdf"
                    onChange={handleFileChange}
                    disabled={isUploading}
                    className="block w-full cursor-pointer rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-700 hover:border-indigo-300 transition-colors file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed"
                />
            </label>

            {isUploading && (
                <p className="mt-4 text-sm text-indigo-600 font-medium">
                    Extracting your profile using Groq AI with Gemini fallback. This may take up to 10-15 seconds.
                </p>
            )}
        </div>
    );
}
