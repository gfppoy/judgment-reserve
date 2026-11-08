# Investigation workspace

Start with `request.md` and `deployment.md`. Inspect `run.py`, `loader.py`, and
`detector.py`. `python run.py` reproduces the submitted initial evaluation;
`python run.py --split reserve` evaluates the reserved capture round.

Data arrays contain images, familiar reference images, evaluation labels
(0 familiar, 1 unfamiliar), and original dataset row identifiers. When recorded
by the capture system, session identifiers are included. Labels are available
for evaluation; the deployment contract specifies what prediction can use.

Images are 8x8 handwritten digits, flattened to 64 values. Familiar classes are
1, 3, 5, 7, and 9. This is a disclosed teaching reconstruction: UCI digit images
with simulated brightness shifts, not actual camera footage. Pixel values are
divided by 16 before shifts; shifted values are not clipped. `reference` contains
100 familiar examples disjoint from the initial and reserve images. All original
digit records are split before capture shifts are applied.

UCI Optical Recognition of Handwritten Digits, Alpaydin & Kaynak (1998),
https://doi.org/10.24432/C50P49, CC BY 4.0. Splits and capture shifts are modified.

The environment already contains Python and NumPy. Save your chosen investigation
scripts and outputs here. No diagnosis or expert verdict is provided in this workspace.
