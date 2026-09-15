# CMU CS Academy Chess Engine
This is a chess engine written in python utilizing an NNUE, bitboards and alpha beta pruning and a full user interface. The engine itself is not particularly strong, the NNUE is very small, utilizing a 768->64x2->1 design. 

## Background Information

The code was written for my AP CSP class on the digital cmu cs academy enviorment. For this reason many odd choices were made in it to keep it working. First off, because CMU CS Academy runs in the browser it uses brython, which lacks support or poorly implements many features of python, odd code designs were made, and perfromance is poor. Running this code in CPython is recommended for that reason. Additionally the single file is anther result of CMU CS Academy which only allows a single file for a project. 

## Running the engine

Running it with a CPython interface is considerably easier, it does require fetching some assets for the pieces, I personally downloaded the ones used right out of chess.com, but honestly its your choice for which pieces you use, just make sure the scaling is correct. If you wish to use the actual editor its much more of a hassel. The edior itself does not allow copy and paste, so you will have to write a cusom request code to the manually push the file up to the editor. This is not very complicated as long as you find your access key, you can just use the requests library in python. 

