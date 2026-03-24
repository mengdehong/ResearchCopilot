import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeHighlight from 'rehype-highlight'
import 'katex/dist/katex.min.css'
import './AcademicMarkdown.css'

interface AcademicMarkdownProps {
    content: string
    onCitationClick?: (refNumber: number) => void
}

/**
 * Renders academic Markdown with:
 * - Standard Markdown syntax
 * - KaTeX inline ($...$) and block ($$...$$) formulas
 * - Syntax-highlighted code blocks
 * - Clickable citation references [1], [2], etc.
 */
export default function AcademicMarkdown({
    content,
    onCitationClick,
}: AcademicMarkdownProps) {
    const processedContent = content.replace(
        /\[(\d+)\]/g,
        (match, num) => `<span class="citation" data-ref="${num}">${match}</span>`,
    )

    return (
        <div className="academic-markdown">
            <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex, rehypeHighlight]}
                components={{
                    span: ({ ...props }) => {
                        const dataRef = (props as Record<string, string>)['data-ref']
                        if (dataRef && onCitationClick) {
                            return (
                                <span
                                    {...props}
                                    className="citation"
                                    onClick={() => onCitationClick(Number(dataRef))}
                                    role="button"
                                    tabIndex={0}
                                />
                            )
                        }
                        return <span {...props} />
                    },
                }}
            >
                {processedContent}
            </ReactMarkdown>
        </div>
    )
}
