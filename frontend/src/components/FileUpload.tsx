import { useState, useRef } from 'react'
import { Upload, File, X } from 'lucide-react'

interface FileUploadProps {
  onFileSelect: (file: File) => void
  accept?: string
  maxSize?: number // in bytes
  multiple?: boolean
  className?: string
  disabled?: boolean
  children?: React.ReactNode
}

export function FileUpload({
  onFileSelect,
  accept = '.log,.txt',
  maxSize = 50 * 1024 * 1024, // 50MB default
  multiple = false,
  className = '',
  disabled = false,
  children
}: FileUploadProps) {
  const [isDragActive, setIsDragActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (disabled) return

    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragActive(true)
    } else if (e.type === 'dragleave') {
      setIsDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (disabled) return

    setIsDragActive(false)
    setError(null)

    const files = Array.from(e.dataTransfer.files)
    processFiles(files)
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabled) return

    setError(null)
    const files = Array.from(e.target.files || [])
    processFiles(files)
  }

  const processFiles = (files: File[]) => {
    if (files.length === 0) return

    const fileToProcess = multiple ? files : files[0]
    
    if (multiple) {
      files.forEach(file => validateAndProcessFile(file))
    } else {
      validateAndProcessFile(fileToProcess as File)
    }
  }

  const validateAndProcessFile = (file: File) => {
    // Check file size
    if (file.size > maxSize) {
      setError(`File size exceeds limit (${formatFileSize(maxSize)})`)
      return
    }

    // Check file type
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase()
    const acceptedExtensions = accept.split(',').map(ext => ext.trim())
    
    if (!acceptedExtensions.includes(fileExtension) && !acceptedExtensions.includes('*')) {
      setError(`File type not accepted. Accepted types: ${accept}`)
      return
    }

    setError(null)
    onFileSelect(file)
  }

  const handleClick = () => {
    if (!disabled) {
      fileInputRef.current?.click()
    }
  }

  const formatFileSize = (bytes: number) => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
  }

  return (
    <div className={className}>
      <div
        className={`
          relative border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors
          ${isDragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-gray-400'}
        `}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={handleClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleFileChange}
          disabled={disabled}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
        
        {children || (
          <div className="space-y-2">
            <Upload className="mx-auto h-12 w-12 text-gray-400" />
            <div className="text-sm text-gray-600">
              <span className="font-medium">Click to upload</span> or drag and drop
            </div>
            <p className="text-xs text-gray-500">
              {accept !== '*' && `${accept} files only`} • Max {formatFileSize(maxSize)}
            </p>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}
    </div>
  )
}

interface FilePreviewProps {
  files: File[]
  onRemove: (index: number) => void
  className?: string
}

export function FilePreview({ files, onRemove, className = '' }: FilePreviewProps) {
  const formatFileSize = (bytes: number) => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {files.map((file, index) => (
        <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
          <div className="flex items-center space-x-3">
            <File className="w-5 h-5 text-gray-400" />
            <div>
              <p className="text-sm font-medium text-gray-900">{file.name}</p>
              <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
            </div>
          </div>
          <button
            onClick={() => onRemove(index)}
            className="p-1 text-gray-400 hover:text-red-600 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  )
}
