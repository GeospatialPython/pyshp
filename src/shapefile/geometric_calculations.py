from __future__ import annotations

from collections.abc import Iterable, Iterator, Reversible

from .exceptions import RingSamplingError
from .types import BBox, Point2D, PointsT, PointT


def signed_area(
    coords: PointsT,
    fast: bool = False,
) -> float:
    """Return the signed area enclosed by a ring using the linear time
    algorithm. A value >= 0 indicates a counter-clockwise oriented ring.
    A faster version is possible by setting 'fast' to True, which returns
    2x the area, e.g. if you're only interested in the sign of the area.
    """
    xs, ys = map(list, list(zip(*coords))[:2])  # ignore any z or m values
    xs.append(xs[1])
    ys.append(ys[1])
    area2: float = sum(xs[i] * (ys[i + 1] - ys[i - 1]) for i in range(1, len(coords)))
    if fast:
        return area2

    return area2 / 2.0


def is_cw(coords: PointsT) -> bool:
    """Returns True if a polygon ring has clockwise orientation, determined
    by a negatively signed area.
    """
    area2 = signed_area(coords, fast=True)
    return area2 < 0


def rewind(coords: Reversible[PointT]) -> PointsT:
    """Returns the input coords in reversed order."""
    return list(reversed(coords))


def ring_bbox(coords: PointsT) -> BBox:
    """Calculates and returns the bounding box of a ring."""
    xs, ys = map(list, list(zip(*coords))[:2])  # ignore any z or m values
    # bbox = BBox(xmin=min(xs), ymin=min(ys), xmax=max(xs), ymax=max(ys))
    # return bbox
    return min(xs), min(ys), max(xs), max(ys)


def bbox_overlap(bbox1: BBox, bbox2: BBox) -> bool:
    """Tests whether two bounding boxes overlap."""
    xmin1, ymin1, xmax1, ymax1 = bbox1
    xmin2, ymin2, xmax2, ymax2 = bbox2
    overlap = xmin1 <= xmax2 and xmin2 <= xmax1 and ymin1 <= ymax2 and ymin2 <= ymax1
    return overlap


def bbox_contains(bbox1: BBox, bbox2: BBox) -> bool:
    """Tests whether bbox1 fully contains bbox2."""
    xmin1, ymin1, xmax1, ymax1 = bbox1
    xmin2, ymin2, xmax2, ymax2 = bbox2
    contains = xmin1 < xmin2 and xmax2 < xmax1 and ymin1 < ymin2 and ymax2 < ymax1
    return contains


def ring_contains_point(coords: PointsT, p: Point2D) -> bool:
    """Fast point-in-polygon crossings algorithm, MacMartin optimization.

    Adapted from code by Eric Haynes
    http://www.realtimerendering.com/resources/GraphicsGems//gemsiv/ptpoly_haines/ptinpoly.c

    Original description:
        Shoot a test ray along +X axis.  The strategy, from MacMartin, is to
        compare vertex Y values to the testing point's Y and quickly discard
        edges which are entirely to one side of the test ray.
    """
    tx, ty = p

    # get initial test bit for above/below X axis
    vtx0 = coords[0]
    yflag0 = vtx0[1] >= ty

    inside_flag = False
    for vtx1 in coords[1:]:
        yflag1 = vtx1[1] >= ty
        # check if endpoints straddle (are on opposite sides) of X axis
        # (i.e. the Y's differ); if so, +X ray could intersect this edge.
        if yflag0 != yflag1:
            xflag0 = vtx0[0] >= tx
            # check if endpoints are on same side of the Y axis (i.e. X's
            # are the same); if so, it's easy to test if edge hits or misses.
            if xflag0 == (vtx1[0] >= tx):
                # if edge's X values both right of the point, must hit
                if xflag0:
                    inside_flag = not inside_flag
            else:
                # compute intersection of pgon segment with +X ray, note
                # if >= point's X; if so, the ray hits it.
                if (
                    vtx1[0] - (vtx1[1] - ty) * (vtx0[0] - vtx1[0]) / (vtx0[1] - vtx1[1])
                ) >= tx:
                    inside_flag = not inside_flag

        # move to next pair of vertices, retaining info as possible
        yflag0 = yflag1
        vtx0 = vtx1

    return inside_flag


def ring_sample(coords: PointsT, ccw: bool = False) -> Point2D:
    """Return a sample point guaranteed to be within a ring, by efficiently
    finding the first centroid of a coordinate triplet whose orientation
    matches the orientation of the ring and passes the point-in-ring test.
    The orientation of the ring is assumed to be clockwise, unless ccw
    (counter-clockwise) is set to True.
    """
    triplet = []

    def itercoords() -> Iterator[PointT]:
        # iterate full closed ring
        yield from coords
        # finally, yield the second coordinate to the end to allow checking the last triplet
        yield coords[1]

    for p in itercoords():
        # add point to triplet (but not if duplicate)
        if p not in triplet:
            triplet.append(p)

        # new triplet, try to get sample
        if len(triplet) == 3:
            # check that triplet does not form a straight line (not a triangle)
            is_straight_line = (triplet[0][1] - triplet[1][1]) * (
                triplet[0][0] - triplet[2][0]
            ) == (triplet[0][1] - triplet[2][1]) * (triplet[0][0] - triplet[1][0])
            if not is_straight_line:
                # get triplet orientation
                closed_triplet = triplet + [triplet[0]]
                triplet_ccw = not is_cw(closed_triplet)
                # check that triplet has the same orientation as the ring (means triangle is inside the ring)
                if ccw == triplet_ccw:
                    # get triplet centroid
                    xs, ys = zip(*triplet)
                    xmean, ymean = sum(xs) / 3.0, sum(ys) / 3.0
                    # check that triplet centroid is truly inside the ring
                    if ring_contains_point(coords, (xmean, ymean)):
                        return xmean, ymean

            # failed to get sample point from this triplet
            # remove oldest triplet coord to allow iterating to next triplet
            triplet.pop(0)

    raise RingSamplingError(
        f"Unexpected error: Unable to find a ring sample point in: {coords}."
        "Ensure the ring's coordinates are oriented clockwise, "
        "and ensure the area enclosed is non-zero. "
    )


def ring_contains_ring(coords1: PointsT, coords2: list[PointT]) -> bool:
    """Returns True if all vertexes in coords2 are fully inside coords1."""
    # Ignore Z and M values in coords2
    return all(ring_contains_point(coords1, p2[:2]) for p2 in coords2)


def organize_polygon_rings(
    rings: Iterable[PointsT], return_errors: dict[str, int] | None = None
) -> list[list[PointsT]]:
    """Organize a list of coordinate rings into one or more polygons with holes.
    Returns a list of polygons, where each polygon is composed of a single exterior
    ring, and one or more interior holes. If a return_errors dict is provided (optional),
    any errors encountered will be added to it.

    Rings must be closed, and cannot intersect each other (non-self-intersecting polygon).
    Rings are determined as exteriors if they run in clockwise direction, or interior
    holes if they run in counter-clockwise direction. This method is used to construct
    GeoJSON (multi)polygons from the shapefile polygon shape type, which does not
    explicitly store the structure of the polygons beyond exterior/interior ring orientation.
    """
    # first iterate rings and classify as exterior or hole
    exteriors = []
    holes = []
    for ring in rings:
        # shapefile format defines a polygon as a sequence of rings
        # where exterior rings are clockwise, and holes counterclockwise
        if is_cw(ring):
            # ring is exterior
            exteriors.append(ring)
        else:
            # ring is a hole
            holes.append(ring)

    # if only one exterior, then all holes belong to that exterior
    if len(exteriors) == 1:
        # exit early
        poly = [exteriors[0]] + holes
        polys = [poly]
        return polys

    # multiple exteriors, ie multi-polygon, have to group holes with correct exterior
    # shapefile format does not specify which holes belong to which exteriors
    # so have to do efficient multi-stage checking of hole-to-exterior containment
    if len(exteriors) > 1:
        # exit early if no holes
        if not holes:
            polys = []
            for ext in exteriors:
                poly = [ext]
                polys.append(poly)
            return polys

        # first determine each hole's candidate exteriors based on simple bbox contains test
        hole_exteriors: dict[int, list[int]] = {
            hole_i: [] for hole_i in range(len(holes))
        }
        exterior_bboxes = [ring_bbox(ring) for ring in exteriors]
        for hole_i in hole_exteriors.keys():
            hole_bbox = ring_bbox(holes[hole_i])
            for ext_i, ext_bbox in enumerate(exterior_bboxes):
                if bbox_contains(ext_bbox, hole_bbox):
                    hole_exteriors[hole_i].append(ext_i)

        # then, for holes with still more than one possible exterior, do more detailed hole-in-ring test
        for hole_i, exterior_candidates in hole_exteriors.items():
            if len(exterior_candidates) > 1:
                # get hole sample point
                ccw = not is_cw(holes[hole_i])
                hole_sample = ring_sample(holes[hole_i], ccw=ccw)
                # collect new exterior candidates
                new_exterior_candidates = []
                for ext_i in exterior_candidates:
                    # check that hole sample point is inside exterior
                    hole_in_exterior = ring_contains_point(
                        exteriors[ext_i], hole_sample
                    )
                    if hole_in_exterior:
                        new_exterior_candidates.append(ext_i)

                # set new exterior candidates
                hole_exteriors[hole_i] = new_exterior_candidates

        # if still holes with more than one possible exterior, means we have an exterior hole nested inside another exterior's hole
        for hole_i, exterior_candidates in hole_exteriors.items():
            if len(exterior_candidates) > 1:
                # exterior candidate with the smallest area is the hole's most immediate parent
                ext_i = sorted(
                    exterior_candidates,
                    key=lambda x: abs(signed_area(exteriors[x], fast=True)),
                )[0]
                hole_exteriors[hole_i] = [ext_i]

        # separate out holes that are orphaned (not contained by any exterior)
        orphan_holes = []
        for hole_i, exterior_candidates in list(hole_exteriors.items()):
            if not exterior_candidates:
                orphan_holes.append(hole_i)
                del hole_exteriors[hole_i]
                continue

        # each hole should now only belong to one exterior, group into exterior-holes polygons
        polys = []
        for ext_i, ext in enumerate(exteriors):
            poly = [ext]
            # find relevant holes
            poly_holes = []
            for hole_i, exterior_candidates in list(hole_exteriors.items()):
                # hole is relevant if previously matched with this exterior
                if exterior_candidates[0] == ext_i:
                    poly_holes.append(holes[hole_i])
            poly += poly_holes
            polys.append(poly)

        # add orphan holes as exteriors
        for hole_i in orphan_holes:
            ext = holes[hole_i]
            # add as single exterior without any holes
            poly = [ext]
            polys.append(poly)

        if orphan_holes and return_errors is not None:
            return_errors["polygon_orphaned_holes"] = len(orphan_holes)

        return polys

    # no exteriors, be nice and assume due to incorrect winding order
    if return_errors is not None:
        return_errors["polygon_only_holes"] = len(holes)
    exteriors = holes
    # add as single exterior without any holes
    polys = [[ext] for ext in exteriors]
    return polys
