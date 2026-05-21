import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import { getWikiGraph, getWikiDetail } from '../api'

interface GraphNode extends d3.SimulationNodeDatum {
  id: string
  label: string
  type: 'paper' | 'concept' | 'entity' | 'note'
  group?: string
  val?: number
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  source: string | GraphNode
  target: string | GraphNode
  type?: string
}

export function WikiGraph() {
  const svgRef = useRef<SVGSVGElement>(null)
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphLink[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [nodeDetail, setNodeDetail] = useState<any>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [physicsEnabled, setPhysicsEnabled] = useState(true)
  const simulationRef = useRef<d3.Simulation<GraphNode, GraphLink> | null>(null)

  // Load Graph Data
  useEffect(() => {
    async function loadGraph() {
      setLoading(true)
      try {
        const data = await getWikiGraph()
        // Map data to ensure safety
        const nodesData: GraphNode[] = (data.nodes || []).map((n: any) => ({
          id: n.id,
          label: n.label || n.id,
          type: n.type || 'concept',
        }))

        // Filter out links with invalid sources/targets
        const nodeIds = new Set(nodesData.map(n => n.id))
        const edgesData: GraphLink[] = (data.edges || [])
          .filter((e: any) => nodeIds.has(e.source) && nodeIds.has(e.target))
          .map((e: any) => ({
            source: e.source,
            target: e.target,
            type: e.type || 'links',
          }))

        setNodes(nodesData)
        setEdges(edgesData)
      } catch (err) {
        console.error('Failed to load wiki graph:', err)
      } finally {
        setLoading(false)
      }
    }
    loadGraph()
  }, [])

  // Load Node Detail when Selected
  useEffect(() => {
    if (!selectedNode) {
      setNodeDetail(null)
      return
    }

    async function loadDetail() {
      setDetailLoading(true)
      try {
        // Map selectedNode.type: paper, concept, entity, note
        const detail = await getWikiDetail(selectedNode!.type, selectedNode!.id)
        setNodeDetail(detail)
      } catch (err) {
        console.error('Failed to load wiki node detail:', err)
        setNodeDetail({
          id: selectedNode!.id,
          type: selectedNode!.type,
          metadata: { title: selectedNode!.label },
          content: 'Failed to load content for this node.'
        })
      } finally {
        setDetailLoading(false)
      }
    }
    loadDetail()
  }, [selectedNode])

  // D3 Force Graph Simulation
  useEffect(() => {
    if (loading || nodes.length === 0 || !svgRef.current) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove() // Clear previous drawings

    const width = svgRef.current.clientWidth || 800
    const height = svgRef.current.clientHeight || 600

    // Add zoom behavior
    const g = svg.append('g')
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 8])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })

    svg.call(zoom)

    // Arrow markers for links
    svg.append('defs').append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 18) // Offset to sit outside node radius
      .attr('refY', 0)
      .attr('markerWidth', 5)
      .attr('markerHeight', 5)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-4L10,0L0,4')
      .attr('fill', 'var(--text-muted)')
      .style('opacity', 0.5)

    // Simulation Setup
    const simulation = d3.forceSimulation<GraphNode>(nodes)
      .force('link', d3.forceLink<GraphNode, GraphLink>(edges).id(d => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-120))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(25))

    simulationRef.current = simulation

    // Link Elements
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(edges)
      .enter()
      .append('line')
      .attr('stroke', 'var(--border-subtle)')
      .attr('stroke-width', 1.2)
      .attr('marker-end', 'url(#arrow)')
      .style('opacity', 0.4)

    // Node Elements Group
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('.node-group')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'node-group')
      .call(d3.drag<SVGGElement, GraphNode>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended)
      )
      .on('click', (event, d) => {
        setSelectedNode(d)
        event.stopPropagation()
      })

    // Node Circle
    node.append('circle')
      .attr('r', d => d.type === 'concept' ? 8 : d.type === 'paper' ? 6 : 5)
      .attr('fill', d => {
        if (d.type === 'concept') return 'var(--accent-coral)'
        if (d.type === 'paper') return 'var(--accent-blue)'
        if (d.type === 'entity') return 'var(--accent-emerald)'
        return 'var(--text-secondary)'
      })
      .attr('stroke', 'var(--bg-primary)')
      .attr('stroke-width', 1.5)

    // Node Label Text
    node.append('text')
      .attr('dx', 12)
      .attr('dy', '.35em')
      .text(d => d.label.length > 25 ? d.label.substring(0, 22) + '...' : d.label)
      .attr('font-size', '0.68rem')
      .attr('fill', 'var(--text-secondary)')
      .style('pointer-events', 'none')
      .style('font-family', 'var(--font-sans)')

    // Simulation updates
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as GraphNode).x!)
        .attr('y1', d => (d.source as GraphNode).y!)
        .attr('x2', d => (d.target as GraphNode).x!)
        .attr('y2', d => (d.target as GraphNode).y!)

      node
        .attr('transform', d => `translate(${d.x!}, ${d.y!})`)
    })

    // Drag handlers
    function dragstarted(event: any, d: GraphNode) {
      if (!event.active && physicsEnabled) simulation.alphaTarget(0.3).restart()
      d.fx = d.x
      d.fy = d.y
    }

    function dragged(event: any, d: GraphNode) {
      d.fx = event.x
      d.fy = event.y
    }

    function dragended(event: any, d: GraphNode) {
      if (!event.active && physicsEnabled) simulation.alphaTarget(0)
      d.fx = null
      d.fy = null
    }

    // Window Resize handler
    const resizeObserver = new ResizeObserver((entries) => {
      if (!entries || entries.length === 0) return
      const { width: w, height: h } = entries[0].contentRect
      simulation.force('center', d3.forceCenter(w / 2, h / 2))
      if (physicsEnabled) simulation.alpha(0.3).restart()
    })
    resizeObserver.observe(svgRef.current)

    return () => {
      simulation.stop()
      resizeObserver.disconnect()
    }
  }, [loading, nodes, edges, physicsEnabled])

  // Apply search query filter
  useEffect(() => {
    if (nodes.length === 0 || !svgRef.current) return

    const query = searchQuery.toLowerCase().trim()
    const svg = d3.select(svgRef.current)

    if (!query) {
      // Reset all nodes opacity
      svg.selectAll('.node-group').style('opacity', 1)
      svg.selectAll('.links line').style('opacity', 0.4)
      return
    }

    svg.selectAll('.node-group').style('opacity', (d: any) => {
      const match = d.label.toLowerCase().includes(query) || d.id.toLowerCase().includes(query)
      return match ? 1 : 0.15
    })

    svg.selectAll('.links line').style('opacity', (d: any) => {
      const sourceMatch = d.source.label?.toLowerCase().includes(query) || d.source.id?.toLowerCase().includes(query)
      const targetMatch = d.target.label?.toLowerCase().includes(query) || d.target.id?.toLowerCase().includes(query)
      return sourceMatch && targetMatch ? 0.6 : 0.05
    })
  }, [searchQuery, nodes])

  // Helper to parse simple markdown to HTML with Obsidian-style links support
  const renderMarkdown = (text: string) => {
    if (!text) return ''
    
    // Convert headers
    let html = text
      .replace(/^### (.*$)/gim, '<h5 style="font-size:0.95rem; font-weight:600; margin-top:12px; margin-bottom:6px;">$1</h5>')
      .replace(/^## (.*$)/gim, '<h4 style="font-size:1.1rem; font-weight:600; margin-top:16px; margin-bottom:8px; border-bottom: 1px solid var(--border-subtle); padding-bottom:4px;">$1</h4>')
      .replace(/^# (.*$)/gim, '<h3 style="font-size:1.3rem; font-weight:700; margin-top:20px; margin-bottom:10px;">$1</h3>')
    
    // Convert bold/italic
    html = html
      .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
      .replace(/\*(.*)\*/gim, '<em>$1</em>')
      
    // Convert lists
    html = html.replace(/^\s*-\s+(.*$)/gim, '<li style="margin-left: 16px; font-size:0.82rem; line-height: 1.5; color: var(--text-secondary);">$1</li>')

    // Obsidian style internal links: [[Node ID|Display Text]] or [[Node ID]]
    html = html.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (match, id, label) => {
      const displayLabel = label || id
      // Return a clickable span that selects the node in the graph
      return `<span class="wiki-inline-link" data-node-id="${id}" style="color:var(--accent-coral); font-weight:500; cursor:pointer; text-decoration:underline;">${displayLabel}</span>`
    })

    return html
  }

  // Handle inline wiki link clicks in the drawer
  const handleContentClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement
    if (target.classList.contains('wiki-inline-link')) {
      const nodeId = target.getAttribute('data-node-id')
      if (nodeId) {
        const found = nodes.find(n => n.id.toLowerCase() === nodeId.toLowerCase() || n.label.toLowerCase() === nodeId.toLowerCase())
        if (found) {
          setSelectedNode(found)
        } else {
          // If not in nodes direct match, try to search
          setSearchQuery(nodeId)
        }
      }
    }
  }

  return (
    <div className="dashboard-container" style={{ display: 'flex', flexDirection: 'row', padding: 0, position: 'relative', overflow: 'hidden' }}>
      
      {/* Graph Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
        
        {/* Search Overlay */}
        <div style={{ position: 'absolute', top: '16px', left: '16px', zIndex: 10, display: 'flex', gap: '8px', alignItems: 'center' }}>
          <div className="search-box" style={{ position: 'relative', minWidth: '220px' }}>
            <input
              type="text"
              placeholder="Search graph nodes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-pill)',
                padding: '8px 12px 8px 34px',
                fontSize: '0.8rem',
                color: 'var(--text-primary)',
                outline: 'none',
              }}
            />
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              style={{ position: 'absolute', left: '12px', top: '11px', color: 'var(--text-tertiary)' }}
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            {searchQuery && (
              <button 
                onClick={() => setSearchQuery('')}
                style={{
                  position: 'absolute', right: '10px', top: '8px', background: 'none', border: 'none', 
                  color: 'var(--text-tertiary)', cursor: 'pointer', padding: '2px'
                }}
              >
                ✕
              </button>
            )}
          </div>

          <button
            onClick={() => {
              setPhysicsEnabled(p => {
                if (simulationRef.current) {
                  if (!p) simulationRef.current.alpha(0.3).restart()
                  else simulationRef.current.stop()
                }
                return !p
              })
            }}
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '8px 12px',
              fontSize: '0.78rem',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 500
            }}
          >
            <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', backgroundColor: physicsEnabled ? 'var(--accent-emerald)' : 'var(--text-muted)' }} />
            {physicsEnabled ? 'Physics: On' : 'Physics: Off'}
          </button>
        </div>

        {/* Node Legends */}
        <div style={{ position: 'absolute', bottom: '16px', left: '16px', zIndex: 10, display: 'flex', gap: '14px', background: 'rgba(var(--bg-primary), 0.65)', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)', padding: '8px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', fontSize: '0.68rem', color: 'var(--text-secondary)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--accent-coral)' }} />
            <span>Concepts</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--accent-blue)' }} />
            <span>Papers</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--accent-emerald)' }} />
            <span>Entities</span>
          </div>
        </div>

        {loading ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)' }}>
            <div style={{ textAlign: 'center' }}>
              <div className="skeleton-avatar" style={{ margin: '0 auto 12px auto', animation: 'skeleton-pulse 1s infinite' }} />
              <span>Loading Wiki Graph...</span>
            </div>
          </div>
        ) : (
          <svg ref={svgRef} style={{ width: '100%', height: '100%', cursor: 'grab' }} />
        )}
      </div>

      {/* Slide-out details drawer */}
      <div 
        style={{
          width: selectedNode ? '380px' : '0px',
          borderLeft: selectedNode ? '1px solid var(--border-subtle)' : 'none',
          background: 'var(--bg-secondary)',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          transition: 'all 240ms cubic-bezier(0.16, 1, 0.3, 1)',
          overflow: 'hidden',
          zIndex: 20
        }}
      >
        {selectedNode && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '380px', flexShrink: 0 }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px', borderBottom: '1px solid var(--border-subtle)' }}>
              <span 
                style={{ 
                  fontSize: '0.62rem', 
                  textTransform: 'uppercase', 
                  letterSpacing: '0.06em', 
                  padding: '2px 8px', 
                  borderRadius: 'var(--radius-pill)', 
                  fontWeight: 600,
                  backgroundColor: selectedNode.type === 'concept' ? 'rgba(255,119,89,0.1)' : 'rgba(24,99,220,0.1)',
                  color: selectedNode.type === 'concept' ? 'var(--accent-coral)' : 'var(--accent-blue)'
                }}
              >
                {selectedNode.type}
              </span>
              <button 
                onClick={() => setSelectedNode(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: '1rem', padding: '4px' }}
                onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-tertiary)'}
              >
                ✕
              </button>
            </div>

            {/* Content Body */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
              {detailLoading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div className="skeleton skeleton-line long" />
                  <div className="skeleton skeleton-line medium" />
                  <div className="skeleton skeleton-line long" />
                  <div className="skeleton skeleton-line short" />
                </div>
              ) : nodeDetail ? (
                <div onClick={handleContentClick}>
                  <h2 style={{ fontSize: '1.25rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '14px', lineHeight: '1.3' }}>
                    {nodeDetail.metadata?.title || selectedNode.label}
                  </h2>
                  
                  {nodeDetail.metadata?.authors && (
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '12px' }}>
                      <strong>Authors:</strong> {Array.isArray(nodeDetail.metadata.authors) ? nodeDetail.metadata.authors.join(', ') : nodeDetail.metadata.authors}
                    </p>
                  )}
                  
                  {nodeDetail.metadata?.categories && (
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '16px' }}>
                      <strong>Categories:</strong> {nodeDetail.metadata.categories}
                    </p>
                  )}

                  <div 
                    className="wiki-markdown-body"
                    style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.6', overflowWrap: 'anywhere' }}
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(nodeDetail.content) }}
                  />
                </div>
              ) : (
                <p style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>No content available</p>
              )}
            </div>
          </div>
        )}
      </div>

    </div>
  )
}
