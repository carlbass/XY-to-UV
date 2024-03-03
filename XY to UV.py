# Author- Carl Bass
# Description- make UV lines from xy lines in sketch
# create a sketch and all the lines, arcs and fitted splines in that sketch 
# will be mapped to the chosen surface in
# a sketch called "'original sketch name' to UV".
# By design, it will not transform construction geometry

import adsk.core, adsk.fusion, adsk.cam, traceback
import os

# Global list to keep all event handlers in scope.
handlers = []

# global variables available in all functions
app = adsk.core.Application.get()
ui  = app.userInterface

# global variables because I can't find a better way to pass this info around -- would be nice if fusion api had some cleaner way to do this
debug = False
swap_uv = False

def run(context):
    try:
        
        # Find where the python file lives and look for the icons in the ./.resources folder
        python_file_folder = os.path.dirname(os.path.realpath(__file__))
        resource_folder = os.path.join (python_file_folder, '.resources')

        # Get the CommandDefinitions collection
        command_definitions = ui.commandDefinitions
        
        tooltip = 'Maps lines, arcs and fitted splines from sketch to surface'

        # Create a button command definition.
        xy_uv_button = command_definitions.addButtonDefinition('XY_to_UV', 'XY to UV', tooltip, resource_folder)
        
        # Connect to the command created event.
        xy_uv_command_created = command_created()
        xy_uv_button.commandCreated.add (xy_uv_command_created)
        handlers.append(xy_uv_command_created)

        # add the Moose Tools and the xy to uv button to the Tools tab
        utilities_tab = ui.allToolbarTabs.itemById('ToolsTab')
        if utilities_tab:
            # get or create the "Moose Tools" panel.
            moose_tools_panel = ui.allToolbarPanels.itemById('MoosePanel')
            if not moose_tools_panel:
                moose_tools_panel = utilities_tab.toolbarPanels.add('MoosePanel', 'Moose Tools')

        if moose_tools_panel:
            # Add the command to the panel.
            control = moose_tools_panel.controls.addCommand(xy_uv_button)
            control.isPromoted = True
            control.isPromotedByDefault = True
            debug_print ('Moose Tools installed')

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# Event handler for the commandCreated event.
class command_created (adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):

        event_args = adsk.core.CommandCreatedEventArgs.cast(args)
        command = event_args.command
        inputs = command.commandInputs
 
        # Connect to the execute event.
        onExecute = command_executed()
        command.execute.add(onExecute)
        handlers.append(onExecute)

        # Connect to the input changed event
        on_input_changed = command_input_changed()
        command.inputChanged.add(on_input_changed)
        handlers.append(on_input_changed)

        # create the sketch selection input
        sketch_selection_input = inputs.addSelectionInput('sketch_select', 'Sketch', 'Select the sketch')
        sketch_selection_input.addSelectionFilter('Sketches')
        sketch_selection_input.setSelectionLimits(1,1)

        # create the face selection input
        face_selection_input = inputs.addSelectionInput('face_select', 'Face', 'Select the face')
        face_selection_input.addSelectionFilter('Faces')
        face_selection_input.setSelectionLimits(1,1)

        # create swap uv checkbox
        inputs.addBoolValueInput('swap_uv', 'Swap u and v', True, '', False)

        # create debug checkbox
        inputs.addBoolValueInput('debug', 'Debug', True, '', False)

# Event handler for the inputChanged event.
class command_input_changed (adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            event_args = adsk.core.InputChangedEventArgs.cast(args)
            inputs = event_args.inputs

            if event_args.input.id == 'sketch_select':
                sketch_selection_input = inputs.itemById('sketch_select')
                if sketch_selection_input.selectionCount == 1:
                    face_selection_input = inputs.itemById ('face_select')
                    face_selection_input.hasFocus = True

        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            
# Event handler for the execute event.
class command_executed (adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        global debug
        global swap_uv

        #eventArgs = adsk.core.CommandEventArgs.cast(args)

        doc = app.activeDocument
        #products = doc.products   
        design = app.activeProduct

        # get current command
        command = args.firingEvent.sender

        #text_palette = ui.palettes.itemById('TextCommands')
        for input in command.commandInputs:
            if (input.id == 'sketch_select'):
                xy_sketch = input.selection(0).entity
            elif (input.id == 'face_select'):
                face = input.selection(0).entity
            elif (input.id == 'swap_uv'):
                swap_uv = input.value           
            elif (input.id == 'debug'):
                debug = input.value           
            else:
                debug_print (f'OOOPS --- too much input')
       
        debug_print (f'----------------- {xy_sketch.name} -----------------')
        debug_print (f'face: {face.objectType}')

        xy_curves =[]
        if (xy_sketch != None):
            sketch_lines = xy_sketch.sketchCurves.sketchLines
            debug_print (f'Processing {sketch_lines.count} lines')

            for line in sketch_lines:
                if line.isConstruction == False:
                    xy_curves.append (line)

            sketch_arcs = xy_sketch.sketchCurves.sketchArcs
            debug_print (f'Processing {sketch_arcs.count} arcs')

            for arc in sketch_arcs:
                if arc.isConstruction == False:
                    xy_curves.append (arc)

            sketch_splines = xy_sketch.sketchCurves.sketchFittedSplines
            debug_print (f'Processing {sketch_splines.count} fitted splines')
            for spline in sketch_splines:
                if spline.isConstruction == False:
                    xy_curves.append (spline)

        # Create a new sketch on the xy plane.
        root_component = design.rootComponent
        sketch = root_component.sketches.add(root_component.xYConstructionPlane)
        if not swap_uv:
            sketch.name = f'UV from {xy_sketch.name}'
        else:
            sketch.name = f'VU from {xy_sketch.name}'

        curves = create_3D_curves (root_component, xy_sketch, face, xy_curves)

        sketch_curves = adsk.fusion.SketchCurves.cast(sketch.sketchCurves)      

        # add the curves to the 3D sketch
        for curve in curves:
            sketch_curves.sketchFixedSplines.addByNurbsCurve(curve)
 

def create_3D_curves (root_component, xy_sketch, face, xy_curves):
    try:        
        # zero out output entity counters
        num_lines = 0
        num_arcs = 0
        num_splines = 0

        # Get the evaluator from the input face.
        surface_evaluator = adsk.core.SurfaceEvaluator.cast(face.evaluator)

        if not swap_uv:
            debug_print (f'NOT swapping u and v')
        else:
            debug_print (f'Swapping u and v')

        # figure out extents of xy_sketch
        xy_range_min = xy_sketch.boundingBox.minPoint
        xy_range_max = xy_sketch.boundingBox.maxPoint
        
        # calculate size of xy sketch; for some reason, sketch bounding box doesn't include points in the calculation

        min_x = 100000
        max_x = -min_x        
        min_y = 100000
        max_y = -min_y
        i = 0
        for p in xy_sketch.sketchPoints:
            if i != 0:
                if p.geometry.x < min_x:
                    min_x = p.geometry.x
                if p.geometry.x > max_x:
                    max_x = p.geometry.x
                if p.geometry.y < min_y:
                    min_y = p.geometry.y
                if p.geometry.y > max_y:
                    max_y = p.geometry.y
            i = i + 1    
            debug_print (f'pt {i} =({p.geometry.x:.3f}, {p.geometry.y:.3f})')
            
        debug_print (f'min x = {min_x:.2f}')
        debug_print (f'max x = {max_x:.2f}')        
        debug_print (f'min y = {min_y:.2f}')
        debug_print (f'max y = {max_y:.2f}')

        x_range = max_x - min_x
        y_range = max_y - min_y

        xy_range_min.x = min_x
        xy_range_min.y = min_y
        xy_range_max.x = max_x
        xy_range_max.y = max_y
        
            
        x_range = xy_range_max.x - xy_range_min.x
        y_range = xy_range_max.y - xy_range_min.y
        z_range = 0.0 #xy_range_max.z - xy_range_min.z  

        debug_print (f'x ranges [{xy_range_min.x:.3f}, {xy_range_max.x:.3f}] = {x_range:.3f}')
        debug_print (f'y ranges [{xy_range_min.y:.3f}, {xy_range_max.y:.3f}] = {y_range:.3f}')
        debug_print (f'z ranges [{xy_range_min.z:.3f}, {xy_range_max.z:.3f}] = {z_range:.3f}')
        
        # find parametric range of face where the mapping will be applied
        uv_range_bounding_box = surface_evaluator.parametricRange()
        uv_range_min = uv_range_bounding_box.minPoint
        uv_range_max = uv_range_bounding_box.maxPoint

        # calculate u and v distances
        u_range = uv_range_max.x - uv_range_min.x
        v_range = uv_range_max.y - uv_range_min.y

        debug_print (f'u ranges [{uv_range_min.x:.3f}, {uv_range_max.x:.3f}] = {u_range:.3f}')
        debug_print (f'v ranges [{uv_range_min.y:.3f}, {uv_range_max.y:.3f}] = {v_range:.3f}')

        # check that xy sketch has non-zero size
        if x_range != 0 and y_range!= 0:
            if not swap_uv:
                x_scale = u_range / x_range
                y_scale = v_range / y_range
            else:
                x_scale = v_range / x_range
                y_scale = u_range / y_range                

            debug_print (f'x scale = {x_scale:.3f}')
            debug_print (f'y scale = {y_scale:.3f}')

        else:
            ui.messageBox('x or y range is 0:\n{}'.format(traceback.format_exc()))

        curves = []
        for xy_curve in xy_curves:     
            count = 0    
            if xy_curve.objectType == 'adsk::fusion::SketchLine':

                start_point = xy_curve.geometry.startPoint
                end_point = xy_curve.geometry.endPoint
                

                if not swap_uv: 
                    x0 = ((start_point.x - xy_range_min.x) * x_scale) + uv_range_min.x
                    x1 = ((end_point.x   - xy_range_min.x) * x_scale) + uv_range_min.x

                    y0 = ((start_point.y - xy_range_min.y) * y_scale) + uv_range_min.y
                    y1 = ((end_point.y   - xy_range_min.y) * y_scale) + uv_range_min.y

                    p0 = adsk.core.Point2D.create (x0, y0)
                    p1 = adsk.core.Point2D.create (x1, y1)  
                else:
                    x0 = ((start_point.x - xy_range_min.x) * x_scale) + uv_range_min.y
                    x1 = ((end_point.x   - xy_range_min.x) * x_scale) + uv_range_min.y

                    y0 = ((start_point.y - xy_range_min.y) * y_scale) + uv_range_min.x
                    y1 = ((end_point.y   - xy_range_min.y) * y_scale) + uv_range_min.x

                    # swap the coordinates 
                    p0 = adsk.core.Point2D.create (y0, x0)
                    p1 = adsk.core.Point2D.create (y1, x1)
                
                debug_print (f'old line ({start_point.x:.3f}, {start_point.y:.3f}) to ({end_point.x:.3f}, {end_point.y:.3f})')            
                debug_print (f'new line ({p0.x:.3f}, {p0.y:.3f}) to ({p1.x:.3f}, {p1.y:.3f})')            
                
                line = adsk.core.Line2D.create(p0, p1)

                collection = surface_evaluator.getModelCurveFromParametricCurve(line)
                count = collection.count

                if count  == 0:
                    debug_print ('Line not created')

                num_lines = num_lines + count

            elif xy_curve.objectType == 'adsk::fusion::SketchArc':

                start_point = xy_curve.geometry.startPoint
                end_point = xy_curve.geometry.endPoint

                if not swap_uv:
                    x0 = ((start_point.x - xy_range_min.x) * x_scale) + uv_range_min.x
                    y0 = ((start_point.y - xy_range_min.y) * y_scale) + uv_range_min.y

                    x2 = ((end_point.x   - xy_range_min.x) * x_scale) + uv_range_min.x
                    y2 = ((end_point.y   - xy_range_min.y) * y_scale) + uv_range_min.y
                else:
                    x0 = ((start_point.x - xy_range_min.x) * x_scale) + uv_range_min.y
                    x2 = ((end_point.x   - xy_range_min.x) * x_scale) + uv_range_min.x

                    y0 = ((start_point.y - xy_range_min.y) * y_scale) + uv_range_min.y
                    y2 = ((end_point.y   - xy_range_min.y) * y_scale) + uv_range_min.x

                # find a point at the midpoint of the arc so we can create an arc with 3 points
                (status, start_parameter, end_parameter) = xy_curve.geometry.evaluator.getParameterExtents()

                (status, midpoint) = xy_curve.geometry.evaluator.getPointAtParameter ((start_parameter + end_parameter) * 0.5)

                if status:
                    if not swap_uv:
                        x1 = ((midpoint.x   - xy_range_min.x) * x_scale) + uv_range_min.x
                        y1 = ((midpoint.y   - xy_range_min.y) * y_scale) + uv_range_min.y

                        p0 = adsk.core.Point2D.create (x0, y0)
                        p1 = adsk.core.Point2D.create (x1, y1)
                        p2 = adsk.core.Point2D.create (x2, y2)                        
                    else:
                        x1 = ((midpoint.x   - xy_range_min.x) * x_scale) + uv_range_min.y
                        y1 = ((midpoint.y   - xy_range_min.y) * y_scale) + uv_range_min.x

                        p0 = adsk.core.Point2D.create (y0, x0)
                        p1 = adsk.core.Point2D.create (y1, x1)
                        p2 = adsk.core.Point2D.create (y2, x2)                          
                else:
                    debug_print (f'Could not eveluate midpoint')

                debug_print (f'xy arc ({start_point.x:.3f}, {start_point.y:.3f}) to ({midpoint.x:.3f}, {midpoint.y:.3f}) to ({end_point.x:.3f}, {end_point.y:.3f})')            
                debug_print (f'uv arc ({p0.x:.3f}, {p0.y:.3f}) to ({p1.x:.3f}, {p1.y:.3f}) to ({p2.x:.3f}, {p2.y:.3f})')            

                arc = adsk.core.Arc2D.createByThreePoints (p0, p1, p2)

                collection = surface_evaluator.getModelCurveFromParametricCurve(arc)

                count = collection.count
                num_arcs = num_arcs + count

            elif xy_curve.objectType == 'adsk::fusion::SketchFittedSpline':

                (status, control_points, degree, knots, is_rational, weights, is_periodic) = xy_curve.geometry.getData()
                
                transformed_points = []

                if not swap_uv:
                    for pt in control_points:             
                        x = ((pt.x - xy_range_min.x) * x_scale) + uv_range_min.x
                        y = ((pt.y - xy_range_min.y) * y_scale) + uv_range_min.y

                        transformed_points.append (adsk.core.Point2D.create(x, y))
                else:
                    for pt in control_points:             

                        x = ((pt.x - xy_range_min.x) * x_scale) + uv_range_min.y
                        y = ((pt.y - xy_range_min.y) * y_scale) + uv_range_min.x

                        transformed_points.append (adsk.core.Point2D.create(y, x))

                if is_rational:
                    spline = adsk.core.NurbsCurve2D.createRational(transformed_points, degree, knots, weights, is_periodic)
                else:
                    spline = adsk.core.NurbsCurve2D.createRational(transformed_points, degree, knots,  is_periodic)

                collection = surface_evaluator.getModelCurveFromParametricCurve (spline)

                count = collection.count
                num_splines = num_splines + 1

            i = 0
            while (i < count):
                curve = collection.item(i)
                if curve.objectType != adsk.core.NurbsCurve3D.classType():
                    curve = curve.asNurbsCurve
                curves.append (curve)   
                i = i + 1

        debug_print (f'{num_lines} lines, {num_arcs} arcs, {num_splines} splines created')

        return curves
    
    except:
        ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

def debug_print (msg):
    if debug:
        text_palette = ui.palettes.itemById('TextCommands')
        text_palette.writeText (msg)
        
def stop(context):
    try:

        # Clean up the UI.
        command_definitions = ui.commandDefinitions.itemById('XY_to_UV')
        if command_definitions:
            command_definitions.deleteMe()
        
        # get rid of this button
        moose_tools_panel = ui.allToolbarPanels.itemById('MoosePanel')
        control = moose_tools_panel.controls.itemById('XY_to_UV')
        if control:
            control.deleteMe()

        # and if it's the last button, get rid of the moose panel
        if moose_tools_panel.controls.count == 0:
                    moose_tools_panel.deleteMe()

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))	