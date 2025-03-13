"use client";
import { useState, useMemo } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { ArrowRight } from "lucide-react";
import { Compare } from "./ui/compare";

interface CodeFile {
  name: string;
  content: string;
  description: string;
}

interface Comparison {
  old: CodeFile;
  new: CodeFile;
}

interface MultiFileCodeCardProps {
  files: Comparison[];
  link: string;
}

export default function MultiFileCodeCard({ files, link }: MultiFileCodeCardProps) {
  // Clean up filenames to remove the "updates to pages/" prefix
  const cleanedFiles = useMemo(() => {
    return files.map(file => {
      // Extract just the base filename without prefixes
      const cleanName = file.old.name.replace(/updates to pages\//, '');
      
      return {
        old: {
          ...file.old,
          name: cleanName
        },
        new: {
          ...file.new,
          name: cleanName
        }
      };
    });
  }, [files]);
  
  // Remove duplicates based on the cleaned names
  const uniqueFiles = useMemo(() => {
    const fileMap = new Map<string, Comparison>();
    
    cleanedFiles.forEach(file => {
      if (!fileMap.has(file.old.name)) {
        fileMap.set(file.old.name, file);
      }
    });
    
    return Array.from(fileMap.values());
  }, [cleanedFiles]);
  
  // Filter out invalid files (files without names)
  const validFiles = uniqueFiles.filter(file => file.old.name && file.new.name);
  
  // Set initial active file if there are valid files
  const [activeFile, setActiveFile] = useState(validFiles.length > 0 ? validFiles[0].old.name : '');
  
  // Calculate total lines for all valid files
  const totalLines = useMemo(() => {
    return validFiles.reduce(
      (acc, file) => acc + (file.new.content ? file.new.content.split("\n").length : 0),
      0
    );
  }, [validFiles]);

  return (
    <Card className="w-full max-w-4xl bg-zinc-800 text-gray-100 border-none">
      <CardHeader>
        <CardTitle className="text-lg font-semibold text-gray-100">
          Code Changes
        </CardTitle>
      </CardHeader>
      <CardContent>
        {validFiles.length > 0 ? (
          <>
            <div className="border-b">
              <ScrollArea className="w-full whitespace-nowrap">
                <div className="flex">
                  {validFiles.map((file, index) => (
                    <button
                      key={`${file.old.name}-${index}`}
                      onClick={() => setActiveFile(file.old.name)}
                      className={`px-4 py-2 text-sm font-medium transition-colors
                        ${
                          activeFile === file.old.name
                            ? "border-b-2 border-primary text-white"
                            : "text-gray-400 hover:text-gray-200"
                        }`}
                    >
                      {file.old.name}
                    </button>
                  ))}
                </div>
                <ScrollBar orientation="horizontal" />
              </ScrollArea>
            </div>
            <div className="mt-4">
              {validFiles.map(
                (file, index) =>
                  file.old.name === activeFile && (
                    <div key={`content-${file.old.name}-${index}`}>
                      <p className="text-sm text-gray-400 mb-2">
                        {file.old.description}
                      </p>
                      <div className="rounded-md overflow-hidden">
                        <Compare
                          beforeCode={file.old.content || "// No content available"}
                          afterCode={file.new.content || "// No content available"}
                          language="javascript"
                          className="h-[250px] w-full md:h-[400px] md:w-full"
                          slideMode="hover"
                        />
                      </div>
                    </div>
                  )
              )}
            </div>
          </>
        ) : (
          <div className="flex justify-center items-center h-64">
            <p className="text-gray-400">No file changes to display</p>
          </div>
        )}
      </CardContent>
      <CardFooter className="flex justify-between items-center border-t border-gray-700/50 pt-4">
        <div className="flex items-center space-x-4">
          <div className="text-center">
            <p className="text-3xl font-bold text-gray-100">{validFiles.length}</p>
            <p className="text-sm text-gray-400">Files Changed</p>
          </div>
          <div className="text-center">
            <p className="text-3xl font-bold text-gray-100">{totalLines}</p>
            <p className="text-sm text-gray-400">Lines Written</p>
          </div>
        </div>
        <Button 
          className="bg-green-600 hover:bg-green-700 text-white transition-all duration-300 transform hover:scale-105" 
          onClick={() => window.open(link, "_blank")}
          disabled={validFiles.length === 0}
        >
          View Pull Request
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </CardFooter>
    </Card>
  );
}