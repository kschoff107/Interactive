/**
 * Transform code structure data from API into React Flow nodes and edges.
 */

/**
 * Transform backend structure data into React Flow format.
 */
export const transformCodeStructureData = (structureData) => {
  if (!structureData) {
    return { nodes: [], edges: [] };
  }

  const nodes = [];
  const edges = [];
  const { modules = [], classes = [], relationships = [] } = structureData;

  // Create module nodes (only if they contain classes)
  const modulesWithClasses = modules.filter(m => m.class_count > 0);
  modulesWithClasses.forEach((mod) => {
    nodes.push({
      id: mod.id,
      type: 'moduleNode',
      data: {
        name: mod.name,
        file_path: mod.file_path,
        class_count: mod.class_count,
        import_count: mod.import_count,
      },
      position: { x: 0, y: 0 },
    });
  });

  // Create class nodes
  classes.forEach((cls) => {
    const methodCount = (cls.methods || []).length;
    const propertyCount = (cls.properties || []).length;
    const visibleMethods = (cls.methods || [])
      .filter(m => m.visibility !== 'dunder')
      .slice(0, 6);

    nodes.push({
      id: cls.id,
      type: 'classNode',
      data: {
        name: cls.name,
        module: cls.module,
        file_path: cls.file_path,
        line_number: cls.line_number,
        base_classes: cls.base_classes || [],
        decorators: cls.decorators || [],
        docstring: cls.docstring || '',
        is_abstract: cls.is_abstract || false,
        is_interface: cls.is_interface || false,
        methods: cls.methods || [],
        properties: cls.properties || [],
        visibleMethods,
        methodCount,
        propertyCount,
      },
      position: { x: 0, y: 0 },
    });

    // Edge from module to class
    const moduleId = `module_${cls.module}`;
    const moduleExists = modulesWithClasses.some(m => m.id === moduleId);
    if (moduleExists) {
      edges.push({
        id: `module-edge-${cls.id}`,
        source: moduleId,
        target: cls.id,
        type: 'smoothstep',
        style: { stroke: '#6b7280', strokeWidth: 1.5 },
        animated: false,
      });
    }
  });

  // Create edges from relationships (inheritance, composition)
  relationships.forEach((rel, index) => {
    const isInheritance = rel.type === 'inheritance';
    edges.push({
      id: `rel-${index}`,
      source: rel.source_id,
      target: rel.target_id,
      label: rel.label || rel.type,
      type: 'smoothstep',
      animated: isInheritance,
      style: {
        stroke: isInheritance ? '#8b5cf6' : '#f59e0b',
        strokeWidth: isInheritance ? 2 : 1.5,
        strokeDasharray: isInheritance ? undefined : '5,5',
      },
      labelStyle: {
        fontSize: '11px',
        fontWeight: 500,
        fill: '#ffffff',
      },
      labelBgStyle: {
        fill: isInheritance ? '#8b5cf6' : '#f59e0b',
        fillOpacity: 0.9,
      },
      labelBgPadding: [6, 3],
      labelBgBorderRadius: 3,
    });
  });

  return { nodes, edges };
};

/**
 * Estimate node height for dagre layout.
 */
export const estimateStructureNodeHeight = (node) => {
  if (node.type === 'moduleNode') {
    return 70;
  }

  if (node.type === 'classNode') {
    const data = node.data || {};
    let height = 60; // header
    const visibleMethods = data.visibleMethods || [];
    const propertyCount = data.propertyCount || 0;

    if (data.base_classes?.length > 0) height += 24;
    if (propertyCount > 0) height += 20 + Math.min(propertyCount, 4) * 18;
    if (visibleMethods.length > 0) height += 20 + visibleMethods.length * 20;
    if ((data.methodCount || 0) > visibleMethods.length) height += 18;

    return Math.max(height, 100);
  }

  return 80;
};

/**
 * Get node width for dagre layout.
 */
export const getStructureNodeWidth = (node) => {
  if (node.type === 'moduleNode') return 200;
  if (node.type === 'classNode') return 260;
  return 220;
};
