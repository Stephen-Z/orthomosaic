import cv2
import numpy as np
import math as m

def importData(fileName, imageDirectory):
    '''
    Arguments:
        fileName: Name of the pose data file in string form e.g. "datasets/imageData.txt"
        imageDirectory: Name of the directory where images arer stored in string form e.g. "datasets/images/"
    Returns:
        dataMatrix: A NumPy ndArray contaning all of the pose data. Each row stores 6 floats containing pose information in XYZYPR form
        allImages: A Python List of NumPy ndArrays containing images.
    '''

    allImages = [] #list of cv::Mat aimghes
    dataMatrix = np.genfromtxt(fileName,delimiter=",",usecols=range(1,7),dtype=float) #read numerical data
    fileNameMatrix = np.genfromtxt(fileName,delimiter=",",usecols=[0],dtype=str) #read filen name strings
    for i in range(0,fileNameMatrix.shape[0]): #read images
        allImages.append(cv2.imread(imageDirectory+fileNameMatrix[i]))
    print "Read data for %i images." % fileNameMatrix.shape[0]
    return dataMatrix, allImages

def computeUnRotMatrix(pose):
    '''
    See http://planning.cs.uiuc.edu/node102.html. Undoes the rotation of the craft relative to the world frame.
    Arguments:
        pose: A 1x6 NumPy ndArray containing pose information in [X,Y,Z,Y,P,R] format
    Returns:
        rot: A 3x3 rotation matrix that removes perspective distortion from the image to which it is applied.
    '''
    a = pose[3]*np.pi/180 #alpha
    b = pose[4]*np.pi/180 #beta
    g = pose[5]*np.pi/180 #gamma
    Rz = np.array(([m.cos(a), -1*m.sin(a),    0],
                   [m.sin(a),    m.cos(a),    0],
                   [       0,           0,     1]))

    Ry = np.array(([ m.cos(b),           0,     m.sin(b)],
                   [        0,           1,            0],
                   [-1*m.sin(b),           0,     m.cos(b)]))

    Rx = np.array(([        1,           0,            0],
                   [        0,    m.cos(g),  -1*m.sin(g)],
                   [        0,    m.sin(g),     m.cos(g)]))
    Ryx = np.dot(Rx,Ry)
    R = np.dot(Rz,Ryx)
    R[0,2] = 0
    R[1,2] = 0
    R[2,2] = 1
    Rtrans = R.transpose()
    InvR = np.linalg.inv(Rtrans)
    return InvR

def display(title, image):
    '''
    OpenCV machinery for showing an image until the user presses a key.
    Arguments:
        title: Window title in string form
        image: ndArray containing image to show
    No returns.
    '''

    cv2.namedWindow(title,cv2.WINDOW_NORMAL)
    cv2.resizeWindow(title,1920,1080)
    cv2.imshow(title,image)
    cv2.waitKey(0)
    cv2.destroyWindow(title)

def drawMatches(img1, kp1, img2, kp2, matches):
    """
    My own implementation of cv2.drawMatches as OpenCV 2.4.9
    does not have this function available but it's supported in
    OpenCV 3.0.0

    This function takes in two images with their associated
    keypoints, as well as a list of DMatch data structure (matches)
    that contains which keypoints matched in which images.

    An image will be produced where a montage is shown with
    the first image followed by the second image beside it.

    Keypoints are delineated with circles, while lines are connected
    between matching keypoints.

    img1,img2 - Grayscale images
    kp1,kp2 - Detected list of keypoints through any of the OpenCV keypoint
              detection algorithms
    matches - A list of matches of corresponding keypoints through any
              OpenCV keypoint matching algorithm
    """

    # Create a new output image that concatenates the two images together
    # (a.k.a) a montage
    rows1 = img1.shape[0]
    cols1 = img1.shape[1]
    rows2 = img2.shape[0]
    cols2 = img2.shape[1]

    out = np.zeros((max([rows1,rows2]),cols1+cols2,3), dtype='uint8')

    # Place the first image to the left
    out[:rows1,:cols1] = np.dstack([img1, img1, img1])

    # Place the next image to the right of it
    out[:rows2,cols1:] = np.dstack([img2, img2, img2])

    # For each pair of points we have between both images
    # draw circles, then connect a line between them
    for match in matches:

        # Get the matching keypoints for each of the images
        img1_idx = match.queryIdx
        img2_idx = match.trainIdx

        # x - columns
        # y - rows
        (x1,y1) = kp1[img1_idx].pt
        (x2,y2) = kp2[img2_idx].pt

        # Draw a small circle at both co-ordinates
        radius = 8
        thickness = 3
        color = (255,0,0) #blue
        cv2.circle(out, (int(x1),int(y1)), radius, color, thickness)
        cv2.circle(out, (int(x2)+cols1,int(y2)), radius, color, thickness)

        # Draw a line in between the two points
        cv2.line(out, (int(x1),int(y1)), (int(x2)+cols1,int(y2)), color, thickness)

    # Also return the image if you'd like a copy
    return out

def warpWithPadding(image,transformation):
    '''
    Produce a "padded" warped image that has black space on all sides so that warped image fits
    Arguments:
        image: ndArray image
        transformation: 3x3 ndArray representing perspective trransformation
    Returns:
        padded: ndArray image enlarged to exactly fit image warped by transformation
    '''

    height = image.shape[0]
    width = image.shape[1]
    corners = np.float32([[0,0],[0,height],[width,height],[width,0]]).reshape(-1,1,2)

    warpedCorners = cv2.perspectiveTransform(corners, transformation)
    [xMin, yMin] = np.int32(warpedCorners.min(axis=0).ravel() - 0.5)
    [xMax, yMax] = np.int32(warpedCorners.max(axis=0).ravel() + 0.5)
    translation = np.array(([1,0,-1*xMin],[0,1,-1*yMin],[0,0,1]))
    fullTransformation = np.dot(translation,transformation)
    result = cv2.warpPerspective(image, fullTransformation, (xMax-xMin, yMax-yMin))

    return result

def merge(refImage, image2,refImgContents):
    '''
    Adds second image to the first image. Assumes images have already been corrected.
    Arguments:
        image1 & image2: ndArrays already processed with computeUnRotMatrix() and warpWithPadding
        image1Contents: list of warped images that make up image 1
    Returns:
        result: second image warped into first image and combined with it
        warpedImage2: second image warped into first image but not combined
    '''

    '''Feature detection and matching'''
    image1 = refImgContents[len(refImgContents)-1]
    detector = cv2.ORB()
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING2, crossCheck=True)
    gray1 = cv2.cvtColor(image1,cv2.COLOR_BGR2GRAY)
    kp1, descriptors1 = detector.detectAndCompute(gray1,None)
    gray2 = cv2.cvtColor(image2,cv2.COLOR_BGR2GRAY)
    kp2, descriptors2 = detector.detectAndCompute(gray2,None)
    matches = matcher.match(descriptors2,descriptors1)
    matchDrawing = drawMatches(gray1,kp1,gray2,kp2,matches)
    display("matches",matchDrawing)
    src_pts = np.float32([ kp2[m.queryIdx].pt for m in matches ]).reshape(-1,1,2)
    dst_pts = np.float32([ kp1[m.trainIdx].pt for m in matches ]).reshape(-1,1,2)
    '''
    for i in range(1,len(refImgContents)):
        image1 = refImgContents[i]
        gray1 = cv2.cvtColor(image1,cv2.COLOR_BGR2GRAY)
        kp1, descriptors1 = detector.detectAndCompute(gray1,None)
        gray2 = cv2.cvtColor(image2,cv2.COLOR_BGR2GRAY)
        kp2, descriptors2 = detector.detectAndCompute(gray2,None)
        matches = matcher.match(descriptors2,descriptors1)
        matchDrawing = drawMatches(gray1,kp1,gray2,kp2,matches)
        display("matches",matchDrawing)
        src_pts = np.concatenate((src_pts,np.float32([ kp2[m.queryIdx].pt for m in matches ]).reshape(-1,1,2)),axis=0)
        dst_pts = np.concatenate((dst_pts,np.float32([ kp1[m.trainIdx].pt for m in matches ]).reshape(-1,1,2)),axis=0)
    '''
    #print src_pts
    '''Compute Affine Transform'''
    A = cv2.estimateRigidTransform(src_pts,dst_pts,fullAffine=False)
    print "A"
    print A

    '''Compute Corners'''
    height1,width1 = refImage.shape[:2]
    height2,width2 = image2.shape[:2]
    corners1 = np.float32(([0,0],[0,height1],[width1,height1],[width1,0]))
    corners2 = np.float32(([0,0],[0,height2],[width2,height2],[width2,0]))
    warpedCorners2 = np.zeros((4,2))
    for i in range(0,4):
        cornerX = corners2[i,0]
        cornerY = corners2[i,1]
        warpedCorners2[i,0] = A[0,0]*cornerX + A[0,1]*cornerY + A[0,2]
        warpedCorners2[i,1] = A[1,0]*cornerX + A[1,1]*cornerY + A[1,2]
    allCorners = np.concatenate((corners1, warpedCorners2), axis=0)
    [xMin, yMin] = np.int32(allCorners.min(axis=0).ravel() - 0.5)
    [xMax, yMax] = np.int32(allCorners.max(axis=0).ravel() + 0.5)

    '''Compute Image Alignment'''
    translation = np.float32(([1,0,-1*xMin],[0,1,-1*yMin],[0,0,1]))
    warpedRefImg = cv2.warpPerspective(refImage, translation, (xMax-xMin, yMax-yMin))
    warpedImageTemp = cv2.warpPerspective(image2, translation, (xMax-xMin, yMax-yMin))
    warpedImage2 = cv2.warpAffine(warpedImageTemp, A, (xMax-xMin, yMax-yMin))
    returnWarpedImage2 = np.copy(warpedImage2)

    refGray = cv2.cvtColor(refImage,cv2.COLOR_BGR2GRAY)
    warpedRefGray = cv2.warpPerspective(refGray, translation, (xMax-xMin, yMax-yMin))
    warpedGrayTemp = cv2.warpPerspective(gray2, translation, (xMax-xMin, yMax-yMin))
    warpedGray2 = cv2.warpAffine(warpedGrayTemp, A, (xMax-xMin, yMax-yMin))

    ret, mask1 = cv2.threshold(warpedRefGray,1,255,cv2.THRESH_BINARY_INV)
    ret, mask2 = cv2.threshold(warpedGray2,1,255,cv2.THRESH_BINARY_INV)

    mask1 = (np.float32(mask1)/255 + 1)/2
    mask2 = (np.float32(mask2)/255 + 1)/2

    warpedRefImg[:,:,0] = warpedRefImg[:,:,0]*mask2
    warpedRefImg[:,:,1] = warpedRefImg[:,:,1]*mask2
    warpedRefImg[:,:,2] = warpedRefImg[:,:,2]*mask2
    warpedImage2[:,:,0] = warpedImage2[:,:,0]*mask1
    warpedImage2[:,:,1] = warpedImage2[:,:,1]*mask1
    warpedImage2[:,:,2] = warpedImage2[:,:,2]*mask1
    result = warpedRefImg + warpedImage2
    display("result",result)
    return result, returnWarpedImage2

    #fullTransformation = np.dot(A,translation)

    #H = cv2.findHomography(src_pts,dst_pts,method=cv2.RANSAC,ransacReprojThreshold=0.1)
    #Homog21 = H[0] #3x3 homography matrix from img2 to img1

    #Homog21 = np.float32(([A[0,0],A[0,1],A[0,2]],[A[1,0],A[1,1],A[1,2]],[0,0,1]))

    #corners1 = np.float32([[0,0],[0,height1],[width1,height1],[width1,0]]).reshape(-1,1,2)
    #corners2 = np.float32([[0,0],[0,height2],[width2,height2],[width2,0]]).reshape(-1,1,2)
    #warpedCorners2 = cv2.warpAffine(corners2,A,(corners2.shape[1],corners2.shape[0]),)#cv2.perspectiveTransform(corners2, Homog21)


    '''
    gray1 = cv2.cvtColor(image1,cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(image2,cv2.COLOR_BGR2GRAY)
    sift = cv2.SIFT()

    # find the keypoints and descriptors with SIFT
    kp1, des1 = sift.detectAndCompute(gray1,None)
    kp2, des2 = sift.detectAndCompute(gray2,None)

    # BFMatcher with default params
    bf = cv2.BFMatcher()
    matches = bf.knnMatch(des2,des1, k=2)
    '''
    '''
    # Apply ratio test
    goodMatches = []
    for m,n in matches:
        #print m
        #print n
        if m.distance < 0.75*n.distance:
            goodMatches.append(m)
    '''

    '''
    print "xMin %f" %xMin
    print "xMax %f" %xMax
    print "yMin %f" %yMin
    print "yMax %f" %yMax
    print "corners"
    print corners
    print "warped corners"
    print warpedCorners
    newWarpedCorners = cv2.perspectiveTransform(corners, fullTransformation)
    print "new warped corners"
    print newWarpedCorners
    '''

    '''
    Compute Corners
    '''
    '''
    #compute corner locations of undistorted rectangular image
    cornersImg = []
    cornersImg.append(np.array(([0],[0],[1])))
    cornersImg.append(np.array(([image.shape[0]],[0],[1])))
    cornersImg.append(np.array(([image.shape[0]],[image.shape[1]],[1])))
    cornersImg.append(np.array(([0],[image.shape[1]],[1])))
    '''
    '''
    #keep track of min and max row and column locations in warped image to know how much to pad original image
    minRLoc = 0
    maxRLoc = image.shape[0]
    minCLoc = 0
    maxCLoc = image.shape[1]
    #store warped corners
    warpedCornersImg = []
    for corner in cornersImg:
        warpedCorner = np.dot(transformation,corner)
        if warpedCorner[0] > maxRLoc:
            maxRLoc = warpedCorner[0]
        if warpedCorner[0] < minRLoc:
            minRLoc = warpedCorner[0]
        if warpedCorner[1] > maxCLoc:
            maxCLoc = warpedCorner[1]
        if warpedCorner[1] < minCLoc:
            minCLoc = warpedCorner[1]
        warpedCornersImg.append(warpedCorner)

    #pts1 = np.float32([[0,0],[0,image.shape[1]],[image.shape[0],image.shape[1]],[,0]]).reshape(-1,1,2)
    print "original corners"
    print cornersImg
    print "warped corners"
    print warpedCornersImg
    '''


    '''
    Compute Padding
    '''
    '''
    topPadding = 0
    bottomPadding = 0
    leftPadding = 0
    rightPadding = 0
    if minRLoc < 0:
        topPadding = abs(minRLoc)
    if minCLoc < 0:
        leftPadding = abs(minCLoc)
    if maxRLoc > image.shape[0]:
        bottomPadding = maxRLoc - image.shape[0]
    if maxCLoc > image.shape[1]:
        rightPadding = maxCLoc - image.shape[1]
    bottomPadding = bottomPadding + topPadding
    rightPadding = rightPadding + leftPadding
    print "minRLoc %f" % minRLoc
    print "top %f" % topPadding
    print "minCLoc %f" % minCLoc
    print "left %f" %leftPadding
    print "maxRLoc %f" % maxRLoc
    print "bottom %f" %bottomPadding
    print "maxCLoc %f" % maxCLoc
    print "right %f" %rightPadding

    xOffset = leftPadding
    yOffset = 0#topPadding
    translation = np.array(([1,0,xOffset],[0,1,yOffset],[0,0,1]))
    TranslatedHomog = np.dot(translation,transformation)

    paddedImg = cv2.copyMakeBorder(image,topPadding,bottomPadding,leftPadding,rightPadding,borderType=cv2.BORDER_CONSTANT,value=(0,0,0))
    warpedImg = cv2.warpPerspective(image,TranslatedHomog,(paddedImg.shape[1],paddedImg.shape[0]),borderMode=cv2.BORDER_CONSTANT,borderValue=(0,0,0))
    return warpedImg
    '''

